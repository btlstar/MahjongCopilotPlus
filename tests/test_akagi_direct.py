# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""A dead environment proxy must not hijack Akagi checks or inference."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import socket
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bot.akagiot.bot_akagiot import BotAkagiOt
from bot.akagiot.engine import MortalEngineAkagiOt
from bot.akagiot.v3 import AkagiV3Client
from gui.preferences import test_ai_connection


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def reply(self,body):
        self.server.paths.append(self.path)
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply({'models':[{'id':'4p-offline','game':'4p'}]} if self.path=='/v3/models' else {'plan':'offline'})

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length',0)))
        if self.path=='/check':
            body = {'result':'success'}
        elif self.path=='/v3/react':
            body = {'model':'4p-offline','reaction':None}
        else:
            body = {'actions':[0],'q_out':[[1]],'masks':[[True]],'is_greedy':[True]}
        self.reply(body)


class AkagiDirectTests(unittest.TestCase):
    def test_v3_legacy_and_ui_checks_ignore_dead_environment_proxy(self):
        with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server, socket.socket() as dead:
            server.paths = []
            worker = threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            self.addCleanup(server.shutdown)
            dead.bind(('127.0.0.1',0))  # Deliberately not listening.
            broken = f'http://127.0.0.1:{dead.getsockname()[1]}'
            environment = {key:broken for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY',
                                                   'http_proxy','https_proxy','all_proxy')}
            environment.update(NO_PROXY='',no_proxy='')
            url = f'http://127.0.0.1:{server.server_port}'
            with patch.dict(os.environ,environment):
                client = AkagiV3Client(url,'offline-key')
                self.addCleanup(client.session.close)
                self.assertEqual(client.catalog()[0]['id'],'4p-offline')
                self.assertEqual(client.react('4p-offline',0,[])['model'],'4p-offline')
                self.assertTrue(client.session.verify)
                BotAkagiOt(url,'offline-key')
                checked = test_ai_connection({'model_type':'AkagiOT','akagi_ot_protocol':'legacy',
                    'akagi_ot_url':url,'akagi_ot_apikey':'offline-key'})
                self.assertIn('检查通过',checked['message'])
                engine = MortalEngineAkagiOt('offline-key',url)
                self.addCleanup(engine.session.close)
                item = SimpleNamespace(tolist=lambda:[0])
                self.assertEqual(engine.react_batch([item],[item],None)[0],[0])
            self.assertTrue({'/v3/key','/v3/models','/v3/react','/check','/react_batch'}<=set(server.paths))


if __name__=='__main__':
    unittest.main()
