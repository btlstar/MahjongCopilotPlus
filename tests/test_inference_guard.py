"""End-to-end wait bounds and game-state recovery, using offline fixtures."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bot.akagiot.v3 import AkagiV3Client
from common.log_helper import LOGGER
from game.game_state import GameState


class InferenceDeadlineTests(unittest.TestCase):
    def test_blocked_network_is_bounded_no_overlap_and_late_result_is_discarded(self):
        client = AkagiV3Client('https://offline.invalid','private-test-key',timeout=.08)
        release,started = threading.Event(),threading.Event()
        calls=[]
        def blocked(*args):
            calls.append(args)
            started.set()
            release.wait(2)
            return {'model':'4p-late','reaction':{'type':'none'}}
        try:
            with patch.object(client,'_request',side_effect=blocked):
                start=time.monotonic()
                with self.assertRaisesRegex(ValueError,'总等待'):
                    client.react('4p-wanted',0,[{'type':'tsumo','pai':'1m'}])
                self.assertTrue(started.is_set())
                self.assertLess(time.monotonic()-start,.7)
                with self.assertRaisesRegex(ValueError,'仍未结束'):
                    client.react('4p-wanted',0,[{'type':'tsumo','pai':'2m'}])
                self.assertEqual(len(calls),1)
                release.set()
                client._pending_react.result(timeout=2)
            expected={'model':'4p-wanted','reaction':{'type':'dahai','pai':'3m'}}
            with patch.object(client,'_request',return_value=expected) as next_call:
                result=client.react('4p-wanted',0,[{'type':'tsumo','pai':'3m'}])
            self.assertEqual(result,expected)
            self.assertEqual(next_call.call_args.args[2]['events'][-1]['pai'],'3m')
        finally:
            release.set()
            if client._pending_react:
                client._pending_react.result(timeout=2)
            client.session.close()

    def test_real_slow_stream_is_bounded_even_with_continuous_socket_activity(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.server.calls+=1
                raw=json.dumps({'model':'4p-wanted','reaction':{'type':'none'},'padding':'x'*1500}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw)))
                self.end_headers()
                try:
                    for offset in range(0,len(raw),32):
                        self.wfile.write(raw[offset:offset+32]); self.wfile.flush()
                        time.sleep(.02)
                except OSError: pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.calls=0
        threading.Thread(target=server.serve_forever,daemon=True).start()
        client=AkagiV3Client(f'http://127.0.0.1:{server.server_port}','offline-key',timeout=.5)
        try:
            start=time.monotonic()
            with self.assertRaisesRegex(ValueError,'总等待'):
                client.react('4p-wanted',0,[])
            self.assertLess(time.monotonic()-start,1.2)
            self.assertEqual(server.calls,1)
            # Let the abandoned network operation drain, without adopting it.
            client._pending_react.result(timeout=3)
        finally:
            client.session.close(); server.shutdown(); server.server_close()


class GameCalculationStateTests(unittest.TestCase):
    def test_exception_releases_calculating_flag_and_expires_old_advice(self):
        state=GameState(SimpleNamespace())
        state.last_reaction={'type':'dahai','pai':'1m'}
        with patch.object(state,'_input_inner',side_effect=ValueError('offline state error')):
            with self.assertRaises(ValueError): state.input({})
        self.assertFalse(state.is_bot_calculating)
        self.assertIsNone(state.get_pending_reaction())
        self.assertEqual(state.last_error,'offline state error')

    def test_nested_sync_input_stays_busy_until_outer_call_finishes(self):
        state=GameState(SimpleNamespace())
        def inner(message):
            self.assertTrue(state.is_bot_calculating)
            if message.get('outer'):
                state.input({})
                self.assertTrue(state.is_bot_calculating)
        with patch.object(state,'_input_inner',side_effect=inner): state.input({'outer':True})
        self.assertFalse(state.is_bot_calculating)

    def test_swallowed_bot_error_is_visible_then_next_decision_recovers(self):
        bot=SimpleNamespace(react=lambda message:None)
        state=GameState(bot)
        with patch.object(bot,'react',side_effect=ValueError('offline timeout')),patch.object(LOGGER,'error'):
            state.mjai_pending_input_msgs=[{'type':'tsumo'}]
            with patch.object(state,'_input_inner',side_effect=lambda msg:state._react_all()):
                self.assertIsNone(state.input({}))
        self.assertFalse(state.is_bot_calculating)
        self.assertEqual(state.last_error,'offline timeout')
        self.assertEqual(state.mjai_pending_input_msgs,[])
        reaction={'type':'dahai','pai':'1m'}
        state.mjai_pending_input_msgs=[{'type':'tsumo'}]
        with patch.object(bot,'react',return_value=reaction):
            with patch.object(state,'_input_inner',side_effect=lambda msg:state._react_all()):
                self.assertEqual(state.input({}),reaction)
        self.assertIsNone(state.last_error)
        self.assertFalse(state.is_bot_calculating)
        self.assertEqual(state.get_pending_reaction(),reaction)


if __name__=='__main__': unittest.main()
