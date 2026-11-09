"""Offline Qt integration check for the native platform; launches no real exe."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from qt_preview import create_application,create_preview,Settings
from qt_desktop_smoke import pump
from common.log_helper import LOGGER


def main():
    LOGGER.setLevel(50)
    app=create_application(); app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for name in ('native.exe','unlock.exe'): (root/name).touch()
        st=Settings(str(root/'settings.json'))
        window=create_preview(st); window.resize(950,680); window.show(); pump(app)
        manager=window.bot_manager
        # Switching a platform never interrupts an active game.
        window.platform_select.setCurrentIndex(window.platform_select.findData('riichicity'))
        assert st.platform=='majsoul' and window._modal is not None
        window._modal.dismiss()
        manager.game_state=None
        window.platform_select.setCurrentIndex(window.platform_select.findData('riichicity'))
        pump(app)
        assert st.platform=='riichicity'
        assert not window.guide_button.isEnabled()
        assert not window.settings_page.fields['enable_overlay'].isEnabled()
        assert window.settings_page.tab_buttons[3].isHidden()
        window.show_page(1); pump(app)
        assert window.wardrobe.native_page.isVisible()
        assert window.wardrobe.majsoul_page.isHidden()
        window.show_settings(4); pump(app)
        fields=window.settings_page.fields
        fields['riichicity_client_path'].setText(str(root/'native.exe'))
        fields['riichicity_unlock_path'].setText(str(root/'unlock.exe'))
        fields['riichicity_unlock_enabled'].setChecked(True)
        fields['riichicity_local_port'].setValue(41110)
        window.settings_page.save_native()
        assert '不能' in window.settings_page.native_result.text()
        assert not st.riichicity_unlock_enabled
        fields['riichicity_local_port'].setValue(10999)
        window.settings_page.save_native()
        assert st.riichicity_unlock_enabled and st.riichicity_client_path==str(root/'native.exe')
        assert manager.mitm_proxinject_need_update
        manager.mitm_proxinject_need_update=False
        with patch.object(manager.native_tools,'start_client') as native,patch.object(manager.browser,'start') as browser,patch.object(manager.mitm_server,'is_running',return_value=True):
            window.open_game(); native.assert_called_once_with(st.riichicity_client_path); browser.assert_not_called()
        for width,height in ((580,520),(760,600),(1100,760)):
            window.resize(width,height); pump(app)
            assert window.settings_page.pages.currentWidget().horizontalScrollBar().maximum()==0
        window.resize(950,680); pump(app)
        output=Path(__file__).resolve().parent.parent/'build'
        output.mkdir(exist_ok=True)
        window.grab().save(str(output/'riichicity-platform.png'))
        window.platform_select.setCurrentIndex(window.platform_select.findData('majsoul'))
        assert st.platform=='majsoul' and window.guide_button.isEnabled()
        assert not window.settings_page.tab_buttons[3].isHidden()
        assert st.riichicity_unlock_enabled # platform changes do not discard settings
        window.close()
        for _ in range(100):
            if window._shutdown_finished: break
            pump(app,.02)
        assert window._shutdown_finished
    print(json.dumps({'ok':True,'checks':['safe platform switch','native wardrobe','disabled unsupported features',
        'private native paths','port conflict validation','native launch dispatch','no browser launch','responsive settings']}))


if __name__=='__main__': main()
