# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Verify real proxy delivery before a small origin response has finished."""
import asyncio
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


class SlowAsset(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self,*args):
        pass

    def do_GET(self):
        chunked = self.path == '/chunked'
        self.send_response(200)
        self.send_header('Content-Type','application/octet-stream')
        self.send_header('Transfer-Encoding' if chunked else 'Content-Length',
                         'chunked' if chunked else '8')
        self.end_headers()
        self.wfile.write(b'4\r\ntile\r\n' if chunked else b'tile')
        self.wfile.flush()
        self.server.release.wait(6)
        try:
            self.wfile.write(b'4\r\ndata\r\n0\r\n\r\n' if chunked else b'data')
            self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):
            pass


async def serve_proxy(port,confdir):
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    from mitm import WSDataInterceptor
    master = DumpMaster(Options(listen_host='127.0.0.1',listen_port=port,confdir=confdir),
                        with_termlog=False,with_dumper=False)
    master.options.update(stream_large_bodies='256k')
    master.addons.add(WSDataInterceptor())
    async def stop_when_requested():
        while True:
            await asyncio.sleep(.05)
            if (Path(confdir)/'stop-requested').exists():
                master.shutdown()
                return
    stop_task = asyncio.create_task(stop_when_requested())
    try:
        await master.run()
    finally:
        stop_task.cancel()


class ProxyStreamingTests(unittest.TestCase):
    def test_small_and_unknown_length_assets_arrive_before_origin_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1',0))
                port = reserve.getsockname()[1]
            with open(Path(directory)/'proxy.log','wb') as output:
                process = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),
                    '--proxy',str(port),directory],cwd=ROOT,stdout=output,stderr=output)
                try:
                    deadline = time.monotonic()+30
                    while True:
                        self.assertIsNone(process.poll(),'Offline proxy failed to start')
                        try:
                            with socket.create_connection(('127.0.0.1',port),timeout=.2):
                                break
                        except OSError:
                            if time.monotonic()>=deadline:
                                self.fail('Offline proxy startup timed out')
                            time.sleep(.05)
                    for path in ('/small','/chunked'):
                        with self.subTest(path=path), ThreadingHTTPServer(('127.0.0.1',0),SlowAsset) as server:
                            server.release = threading.Event()
                            worker = threading.Thread(target=server.serve_forever,daemon=True)
                            worker.start()
                            client = http.client.HTTPConnection('127.0.0.1',port,timeout=2)
                            try:
                                client.request('GET',f'http://127.0.0.1:{server.server_port}{path}')
                                response = client.getresponse()
                                self.assertEqual(response.status,200)
                                self.assertEqual(response.read(4),b'tile')
                                self.assertFalse(server.release.is_set())
                                server.release.set()
                                self.assertEqual(response.read(),b'data')
                            finally:
                                server.release.set()
                                client.close()
                                server.shutdown()
                                worker.join(timeout=2)
                finally:
                    # Let both the Windows venv launcher and its interpreter
                    # exit normally before TemporaryDirectory removes the log.
                    (Path(directory)/'stop-requested').touch()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--proxy':
        asyncio.run(serve_proxy(int(sys.argv[2]),sys.argv[3]))
    else:
        unittest.main()
