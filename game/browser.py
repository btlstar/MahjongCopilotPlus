# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
""" Game Broswer class for controlling maj-soul web client operations"""
import logging
import time
import threading
import queue

from io import BytesIO
from playwright._impl._errors import TargetClosedError
from playwright.sync_api import sync_playwright, BrowserContext, Page
from common import utils
from common.utils import Folder, FPSCounter, list_children
from common.log_helper import LOGGER
from .viewport import fit_game_rect
from .guide_overlay import RENDER_GUIDE

class GameBrowser:
    """ Wrapper for Playwright browser controlling maj-soul operations
    Browser runs in a thread, and actions are queued to be processed by the thread"""

    def __init__(self, width:int, height:int):
        """ Set browser with viewport size (width, height)"""
        self.width = width
        self.height = height
        self.resizable = True
        self.game_left = 0
        self.game_top = 0
        self.geometry_revision = 0
        self._action_queue = queue.Queue()       # thread safe queue for actions
        self._stop_event = threading.Event()    # set this event to stop processing actions
        self._browser_thread = None

        self.init_vars()

    def init_vars(self):
        """ initialize internal variables"""
        self.context:BrowserContext = None
        self.page:Page = None        # playwright page, only used by thread
        self.fps_counter = FPSCounter()

        # for tracking page info
        self._page_title:str = None
        self._last_update_time:float = 0
        self.zoomlevel_check:float = None
        self._page_ready = False
        self._context_closed = False
        self.last_page_error = None
        self._navigation_http_error = None
        self._last_page_error_log = float('-inf')

        # overlay info
        self._canvas_id = None              # for overlay
        self._overlay_enabled = True
        self._last_botleft_text = None
        self._last_guide = None
        self._overlay_start_pending = False

    def __del__(self):
        self.stop()

    def start(self, url:str, proxy:str=None, width:int=None, height:int=None,
              enable_chrome_ext:bool=False, resizable:bool=True):
        """ Launch the browser in a thread, and start processing action queue
        params:
            url(str): url of the page to open upon browser launch
            proxy(str): proxy server to use. e.g. http://1.2.3.4:555"
            width, height: viewport width and height
            enable_ext: True to enable chrome extensions
        """
        # using thread here to avoid playwright sync api not usable in async context (textual) issue
        if self.is_running():
            logging.info('Browser already running.')
            return
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
        self.resizable = resizable
        self.game_left = self.game_top = 0
        self._clear_action_queue()
        self._stop_event.clear()
        self._browser_thread = threading.Thread(
            target=self._run_browser_and_action_queue,
            args=(url, proxy, enable_chrome_ext),
            name="BrowserThread",
            daemon=True)
        self._browser_thread.start()


    def _launch_options(self,proxy,enable_chrome_ext=False):
        """Shared launch policy for normal and extension-enabled game windows."""
        args = ['--noerrdialogs','--test-type=webdriver',
                f'--window-size={int(self.width)},{int(self.height) + 88}']
        if enable_chrome_ext:
            extensions_list = list_children(Folder.CHROME_EXT, True, False, True)
            LOGGER.info('Extensions loaded: %s', extensions_list)
            args += ['--disable-extensions-except='+','.join(extensions_list),
                     '--load-extension='+','.join(extensions_list)]
        return dict(
            user_data_dir=utils.sub_folder(Folder.BROWSER_DATA),
            headless=False,
            chromium_sandbox=True,
            viewport=None if self.resizable else {'width':self.width,'height':self.height},
            no_viewport=self.resizable,
            proxy={'server':proxy} if proxy else None,
            ignore_default_args=['--enable-automation'],
            args=args)

    def _run_browser_and_action_queue(self, url:str, proxy:str, enable_chrome_ext:bool=False):
        """ run browser and keep processing action queue (blocking)"""
        LOGGER.info('Starting Chromium, viewport=%dx%d, proxy=%s', self.width, self.height, proxy)
        with sync_playwright() as playwright:
            try:
                self.context = playwright.chromium.launch_persistent_context(
                    **self._launch_options(proxy,enable_chrome_ext))
            except Exception as e:
                LOGGER.error('Error launching the browser: %s', e, exc_info=True)
                return

            try:
                self._open_initial_page(url)
            except Exception as e:
                self.last_page_error = '游戏网页未能打开，可在浏览器中刷新重试；网络详情见诊断。'
                LOGGER.warning('Initial navigation failed; keeping browser open for retry: %s',e)

            # # Do not allow new page tab
            # def on_page(page:Page):
            #     LOGGER.info("Closing additional page. Only one Majsoul page is allowed")
            #     page.close()

            # if not enable_extensions:
            #     self.context.on("page", on_page)

            # keep running actions until stop event is set
            while self._stop_event.is_set() is False:
                self.fps_counter.frame()
                if not self._browser_step():
                    break
                time.sleep(0.002)

            # stop event is set: close browser
            LOGGER.debug("Closing browser")
            try:
                if self.page.is_closed() is False:
                    self.page.close()
                if self.context:
                    self.context.close()
            except TargetClosedError as e:
                # ok if closed already
                pass
            except Exception as e:
                LOGGER.error('Error closing browser: %s', e ,exc_info=True)
            self.init_vars()
        return

    def _open_initial_page(self,url):
        """Navigate an existing blank startup page; preserve restored user tabs."""
        blank = next((page for page in self.context.pages
                      if not page.is_closed() and page.url in ('about:blank','chrome://newtab/','chrome://new-tab-page/')),None)
        self.page = blank if blank is not None else self.context.new_page()
        self._bind_page_events()
        self.page.goto(url,wait_until='domcontentloaded')

    def _bind_page_events(self):
        self.context.on('close',lambda *_:self._on_context_closed())
        self.page.on('domcontentloaded',self._on_document_ready)
        self.page.on('response',self._on_navigation_response)
        self.page.on('crash',self._on_page_crashed)

    def _on_context_closed(self):
        self._context_closed = True

    def _forget_overlay(self):
        self._canvas_id = None
        self._last_guide = None
        self._last_botleft_text = None

    def _on_document_ready(self):
        # A new document has no DOM nodes from the previous one. Same-document
        # hash/history changes do not fire DOMContentLoaded.
        self._forget_overlay()
        self._page_ready = False
        self._page_title = None
        self.zoomlevel_check = None
        self._last_update_time = 0

    def _on_navigation_response(self,response):
        if response.request.is_navigation_request() and response.frame==self.page.main_frame:
            self._navigation_http_error = (f'游戏网页加载失败（HTTP {response.status}），可刷新重试。'
                                           if response.status>=400 else None)
            self.last_page_error = self._navigation_http_error

    def _on_page_crashed(self):
        self._page_ready = False
        self._forget_overlay()
        self.last_page_error = '游戏标签页异常，可在浏览器中刷新重试。'
        LOGGER.warning('Game renderer reported a crash; browser window retained for recovery')

    def _poll_page(self):
        """Probe the current document on the Playwright worker thread only."""
        state = self.page.evaluate("""(id) => {
            const overlay = !!id && !!document.getElementById(id);
            if (id && !overlay) document.getElementById(id+'-guide')?.remove();
            return {title: document.title, zoom: window.devicePixelRatio,
                ready: document.readyState !== 'loading' && !!document.body,
                overlay, guide: !!id && !!document.getElementById(id+'-guide')};
        }""",self._canvas_id)
        if self._canvas_id and not state['overlay']:
            self._forget_overlay()
        elif self._last_guide is not None and not state.get('guide',False):
            self._last_guide = None
        self._page_title = state['title']
        self._page_ready = bool(state['ready'] and not self._navigation_http_error
                                and self.page.url.startswith(('http://','https://')))
        self.zoomlevel_check = state['zoom'] if self._page_ready else None
        if self._page_ready:
            self.last_page_error = None
        if self._page_ready and self.resizable:
            self._sync_game_geometry()

    def _browser_step(self):
        """Only an actual close stops the browser, not a navigation exception."""
        if self._context_closed or self.page is None or self.page.is_closed():
            return False
        now = time.monotonic()
        if now-self._last_update_time>0.25:
            self._last_update_time = now
            try:
                self._poll_page()
            except Exception as error:
                self._page_ready = False
                self._page_title = None
                self.zoomlevel_check = None
                self.last_page_error = '网页正在重新加载或暂时不可用，可在浏览器中刷新重试。'
                if now-self._last_page_error_log>=5:
                    LOGGER.warning('Page probe interrupted; waiting for recovery: %s',error)
                    self._last_page_error_log = now
        try:
            action = self._action_queue.get_nowait()
            action()
        except queue.Empty:
            pass
        except Exception as error:
            # Navigation can invalidate an action's JS context too. Do not
            # close the window; the next page probe reconciles DOM state.
            LOGGER.warning('Browser action interrupted; window retained: %s',error)
        return True

    def _sync_game_geometry(self):
        dimensions = self.page.evaluate("""() => {
            const canvas = document.querySelector('#layaCanvas, #unity-canvas');
            const box = canvas ? canvas.getBoundingClientRect() : null;
            return {width: innerWidth, height: innerHeight,
                canvas: box ? {x: box.x, y: box.y, width: box.width, height: box.height} : null};
        }""")
        rect = fit_game_rect(dimensions['width'], dimensions['height'], dimensions['canvas'])
        previous = (self.game_left, self.game_top, self.width, self.height)
        if all(abs(a - b) < 1 for a, b in zip(rect, previous)):
            return
        self.game_left, self.game_top, self.width, self.height = rect
        self.geometry_revision += 1
        if self.is_overlay_working():
            guide, status = self._last_guide, self._last_botleft_text
            self._action_stop_overlay()
            self._action_start_overlay()
            if guide:
                self._action_overlay_update_guide(*guide)
            if status:
                self._action_overlay_update_botleft(status)

    def _clear_action_queue(self):
        """ Clear the action queue"""
        while True:
            try:
                self._action_queue.get_nowait()
            except queue.Empty:
                break

    def stop(self, join_thread:bool=False):
        """ Shutdown browser thread"""
        if self.is_running():
            self._stop_event.set()
            if join_thread:
                self._browser_thread.join()
            self._browser_thread = None

    def is_running(self):
        """ return True if browser thread is still running"""
        if self._browser_thread and self._browser_thread.is_alive():
            return True
        return False

    def bring_to_front(self):
        """Keep all Playwright calls on the browser's own thread."""
        if self.is_running():
            self._action_queue.put(lambda:self.page.bring_to_front())

    def is_page_normal(self):
        """ return True if page is loaded """
        return self.page is not None and self._page_ready

    def is_overlay_working(self):
        """ return True if overlay is on and working"""
        if self.page is None:
            return False
        if self._canvas_id is None:
            return False
        return True

    def mouse_move(self, x:int, y:int, steps:int=5, blocking:bool=False):
        """ Queue action: mouse move to (x,y) on viewport
        if block, wait until action is done"""
        finish_event = threading.Event()
        self._action_queue.put(lambda: self._action_mouse_move(x, y, steps, finish_event))
        if blocking:
            finish_event.wait()

    def mouse_click(self, delay:float=80, blocking:bool=False):
        """ Queue action: mouse click at (x,y) on viewport
        if block, wait until action is done"""
        finish_event = threading.Event()
        self._action_queue.put(lambda: self._action_mouse_click(delay, finish_event))
        if blocking:
            finish_event.wait()

    def mouse_down(self, blocking:bool=False):
        """ Queue action: mouse down on page"""
        finish_event = threading.Event()
        self._action_queue.put(lambda: self._action_mouse_down(finish_event))
        if blocking:
            finish_event.wait()

    def mouse_up(self,blocking:bool=False):
        """ Queue action: mouse up on page"""
        finish_event = threading.Event()
        self._action_queue.put(lambda: self._action_mouse_up(finish_event))
        if blocking:
            finish_event.wait()

    def mouse_wheel(self, dx:float, dy:float, blocking:bool=False):
        """ Queue action for mouse wheel"""
        finish_event = threading.Event()
        self._action_queue.put(lambda: self._action_mouse_wheel(dx, dy, finish_event))
        if blocking:
            finish_event.wait()

    def auto_hu(self):
        """ Queue action: Autohu action"""
        self._action_queue.put(self._action_autohu)

    def start_overlay(self):
        """ Queue action: Start showing the overlay"""
        self._overlay_enabled = True
        if self._overlay_start_pending or self.is_overlay_working():
            return
        self._overlay_start_pending = True
        def start():
            try:
                self._action_start_overlay()
            finally:
                self._overlay_start_pending = False
        self._action_queue.put(start)

    def stop_overlay(self):
        """ Queue action: Stop showing the overlay"""
        was_enabled = self._overlay_enabled
        self._overlay_enabled = False
        if was_enabled or self.is_overlay_working():
            self._action_queue.put(self._action_stop_overlay)

    def overlay_update_guidance(self, guide_str:str, option_subtitle:str, options:list, rich_rows=None):
        """ Queue action: update text area
        params:
            guide_str(str): AI guide str (recommendation action)
            option_subtitle(str): subtitle for options (display before option list)
            options(list): list of (str, float), indicating action/tile with its probability """
        if self._last_guide == (guide_str, option_subtitle, options, rich_rows):  # skip if same guide
            return
        self._action_queue.put(lambda: self._action_overlay_update_guide(guide_str, option_subtitle, options, rich_rows))

    def overlay_clear_guidance(self):
        """ Queue action: clear overlay text area"""
        if self._last_guide is None:  # skip if already cleared
            return
        self._action_queue.put(self._action_overlay_clear_guide)

    def overlay_update_botleft(self, text:str):
        """ update bot-left corner text area
        params:
            text(str): Text, can have linebreak '\n'. None to clear text
        """
        if text == self._last_botleft_text:     # skip if same text
            return
        self._action_queue.put(lambda: self._action_overlay_update_botleft(text))


    def screen_shot(self) -> bytes | None:
        """ Take broswer page screenshot and return buff if success, or None if not"""
        if not self.is_page_normal():
            return None
        res_queue = queue.Queue()
        try:
            self._action_queue.put(lambda: self._action_screen_shot(res_queue))
            res:BytesIO = res_queue.get(True,5)
        except queue.Empty:
            return None
        except Exception as e:
            LOGGER.error("Error taking screenshot: %s", e, exc_info=True)
            return None

        if res is None:
            return None
        else:
            return res

    def _action_mouse_move(self, x:int, y:int, steps:int, finish_event:threading.Event):
        """ move mouse to (x,y) with steps, and set finish_event when done"""
        try:
            self.page.mouse.move(x=x + self.game_left, y=y + self.game_top, steps=steps)
        finally:
            finish_event.set()

    def _action_mouse_click(self, delay:float, finish_event:threading.Event):
        """ mouse click on page at (x,y)"""
        # self.page.mouse.click(x=x, y=y, delay=delay)
        self.page.mouse.down()
        time.sleep(delay/1000)
        self.page.mouse.up()
        finish_event.set()

    def _action_mouse_down(self, finish_event:threading.Event):
        """ mouse down on page"""
        self.page.mouse.down()
        finish_event.set()

    def _action_mouse_up(self, finish_event:threading.Event):
        """ mouse up on page"""
        self.page.mouse.up()
        finish_event.set()

    def _action_mouse_wheel(self, dx:float, dy:float, finish_event:threading.Event):
        self.page.mouse.wheel(dx, dy)
        finish_event.set()

    def _action_autohu(self):
        """ call autohu function in page"""
        self.page.evaluate("() => view.DesktopMgr.Inst.setAutoHule(true)")

    def _action_start_overlay(self):
        """ Display overlay on page. Will ignore if already exist, or page is None"""
        if not self._overlay_enabled or self.page is None:
            return
        if self.is_overlay_working():   # skip if overlay already working
            return
        canvas_id = utils.random_str(8)
        js_code = f"""(() => {{
            if (!document.body || document.readyState === 'loading') return false;
            // Create a canvas element and add it to the document body
            const canvas = document.createElement('canvas');
            canvas.id = '{canvas_id}';
            canvas.width = {self.width}; // Width of the canvas
            canvas.height = {self.height}; // Height of the canvas
            
            // Set styles to ensure the canvas is on top
            canvas.style.position = 'fixed'; // Use 'fixed' or 'absolute' positioning
            canvas.style.left = '{self.game_left}px';
            canvas.style.top = '{self.game_top}px';
            canvas.style.zIndex = '9999999'; // High z-index to ensure it is on top
            canvas.style.pointerEvents = 'none'; // Make the canvas click-through
            document.body.appendChild(canvas);
            return true;
            }})()"""
        if self.page.evaluate(js_code):
            self._canvas_id = canvas_id
            self._last_guide = None
            self._last_botleft_text = None

    def _action_stop_overlay(self):
        """ Remove overlay from page"""

        if self.is_overlay_working() is False:
            return
        js_code = f"""(() => {{
            const canvas = document.getElementById('{self._canvas_id}');
            if (canvas) {{
                canvas.remove();
            }}
            document.getElementById('{self._canvas_id}-guide')?.remove();
            }})()"""
        self.page.evaluate(js_code)
        self._canvas_id = None
        self._last_botleft_text = None
        self._last_guide = None

    def _action_overlay_update_guide(self, line1: str, option_title: str, options: list[tuple[str, float]], rich_rows=None):
        if not self._overlay_enabled or not self.is_overlay_working():
            return
        if rich_rows is None:
            from common.presentation import advice_rows
            from common.lan_str import LanStrZHS
            rich_rows = advice_rows(line1,options or [],LanStrZHS())
        rendered = self.page.evaluate(RENDER_GUIDE, {
            'id': f'{self._canvas_id}-guide', 'line': line1, 'options': options or [],
            'ownerId':self._canvas_id,
            'left': self.game_left, 'top': self.game_top, 'width': self.width, 'height': self.height,
            'rows': rich_rows,
        })
        if rendered is False:
            self._forget_overlay()
            return
        self._last_guide = (line1, option_title, options, rich_rows)

    def _action_overlay_clear_guide(self):
        if not self.is_overlay_working():
            return
        self.page.evaluate('(id) => document.getElementById(id)?.remove()', f'{self._canvas_id}-guide')
        self._last_guide = None

    def _action_overlay_update_botleft(self, text:str=None):
        if self.is_overlay_working() is False:
            return

        font_size = int(self.height/48)
        box_top = 0.885
        box_left = 0
        box_width = 0.115
        box_height = 1- box_top

        # Escape JavaScript special characters and convert newlines
        js_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') if text else ''

        js_code = f"""(() => {{
            // find canvas context
            const canvas = document.getElementById('{self._canvas_id}');
            if (!canvas || !canvas.getContext) {{
                return;
            }}
            const ctx = canvas.getContext('2d');  
            
            // clear box          
            const box_left = canvas.width * {box_left};
            const box_top = canvas.height * {box_top};
            const box_width = canvas.width * {box_width};
            const box_height = canvas.height * {box_height};
            ctx.clearRect(box_left, box_top, box_width, box_height);
            
            // draw text
            const text = "{js_text}"
            if (!text) {{
                return; // Skip drawing if text is empty
            }}
            ctx.fillStyle = "rgba(0, 0, 0, 0.2)";
            ctx.fillRect(box_left, box_top, box_width, box_height);
            
            ctx.fillStyle = "#FFFFFF";
            ctx.textBaseline = "top"
            ctx.font = "{font_size}px Arial";
            
            // Split text into lines and draw each line
            const lines = text.split('\\n');
            const textX = {font_size} * 0.25
            let startY = canvas.height * {box_top} + {font_size}*0.5;
            const lineHeight = {font_size} * 1.2; // Adjust line height as needed
            lines.forEach((line, index) => {{
                ctx.fillText(line, canvas.width * {box_left} + textX, startY + (lineHeight * index));
            }});            
        }})()"""
        self.page.evaluate(js_code)
        self._last_botleft_text = text

    def _overlay_update_indicators(self, bars:list):
        """ Update the indicators on overlay """
        # TODO
        for x,y,height in bars:
            pass


    def _action_screen_shot(self, res_queue:queue.Queue, time_ms:int=5000):
        """ take screen shot from browser page
        Params:
            res_queue: queue for saving the image buff data"""
        if self.is_page_normal():
            try:
                ss_bytes:BytesIO = self.page.screenshot(timeout=time_ms, clip={
                    'x': self.game_left, 'y': self.game_top, 'width': self.width, 'height': self.height})
                res_queue.put(ss_bytes)
            except Exception as e:
                LOGGER.error("Error taking screenshot: %s", e, exc_info=True)
                res_queue.put(None)
        else:
            res_queue.put(None)
            LOGGER.debug("Page not loaded, no screenshot")
