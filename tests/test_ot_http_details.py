# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Redirect method/auth boundaries and optional legacy inference metadata."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import requests

from bot.akagiot.v3 import AkagiV3Client
from bot.akagiot.engine import MortalEngineAkagiOt
from bot.akagiot.bot_akagiot import BotAkagiOt
from bot.akagiot.model_report import inference_model_report


def response(status=200,headers=None,body=None):
    return SimpleNamespace(status_code=status,headers=headers or {},json=lambda:body or {'models':[]},raise_for_status=lambda:None)


class V3HttpTests(unittest.TestCase):
    def setUp(self):
        self.client = AkagiV3Client('https://api.example.invalid','offline-key')
        self.addCleanup(self.client.session.close)

    def test_same_origin_308_preserves_post_body_and_authorization(self):
        reply = response(body={'model':'4p-test'})
        with patch.object(self.client.session,'request',side_effect=[response(308,{'Location':'/v3/react/'}),reply]) as call:
            self.client.react('4p-test',1,[{'type':'none'}])
        first,last = call.call_args_list
        self.assertEqual(last.args,('POST','https://api.example.invalid/v3/react/'))
        self.assertEqual(first.kwargs['json'],last.kwargs['json'])
        self.assertEqual(last.kwargs['headers']['Authorization'],'Bearer offline-key')
        self.assertFalse(last.kwargs['allow_redirects'])

    def test_same_origin_get_redirect_retains_authorization(self):
        with patch.object(self.client.session,'request',side_effect=[response(308,{'Location':'/v3/key/'}),response()]) as call:
            self.client._request('GET','/v3/key')
        self.assertEqual(call.call_args.args,('GET','https://api.example.invalid/v3/key/'))

    def test_cross_origin_redirects_never_send_a_second_request(self):
        for target in ('https://other.invalid/v3/key','http://api.example.invalid/v3/key','https://api.example.invalid:444/v3/key','https://user:pass@api.example.invalid/v3/key'):
            with self.subTest(target=target),patch.object(self.client.session,'request',return_value=response(308,{'Location':target})) as call:
                with self.assertRaisesRegex(ValueError,'未转发密钥'):
                    self.client._request('GET','/v3/key')
                self.assertEqual(call.call_count,1)

    def test_post_302_is_not_changed_to_get(self):
        with patch.object(self.client.session,'request',return_value=response(302,{'Location':'/v3/react/'})) as call:
            with self.assertRaisesRegex(ValueError,'未改成 GET'):
                self.client.react('4p-test',0,[])
        self.assertEqual(call.call_count,1)

    def test_redirect_loop_is_bounded_and_missing_location_is_explained(self):
        with patch.object(self.client.session,'request',return_value=response(308,{'Location':'/v3/key'})) as call:
            with self.assertRaisesRegex(ValueError,'次数过多'):
                self.client._request('GET','/v3/key')
            self.assertEqual(call.call_count,4)
        with patch.object(self.client.session,'request',return_value=response(308)):
            with self.assertRaisesRegex(ValueError,'没有提供'):
                self.client._request('GET','/v3/key')

    def test_network_errors_do_not_echo_sensitive_exception_content(self):
        for error,expected in ((requests.exceptions.SSLError('offline-key'),'证书'),
                               (requests.exceptions.ProxyError('offline-key'),'代理'),
                               (requests.exceptions.Timeout('offline-key'),'超时'),
                               (requests.exceptions.ConnectionError('offline-key'),'网络')):
            with self.subTest(error=type(error)),patch.object(self.client.session,'request',side_effect=error):
                with self.assertRaisesRegex(ValueError,expected) as caught:
                    self.client._request('GET','/v3/key')
                self.assertNotIn('offline-key',str(caught.exception))

    def test_html_auth_and_rate_limit_errors_are_distinct(self):
        for status,headers,expected in ((403,{'Content-Type':'text/html'},'网页'),(401,{},'授权'),(429,{},'限流'),(404,{},'接口不存在')):
            with self.subTest(status=status),patch.object(self.client.session,'request',return_value=response(status,headers)):
                with self.assertRaisesRegex(ValueError,expected):
                    self.client._request('GET','/v3/key')


class LegacyReportTests(unittest.TestCase):
    def test_missing_metadata_does_not_guess_architecture_or_default(self):
        model,note = inference_model_report({'version':4,'q_out':[[0]*46],'result':'success'}, {})
        self.assertIsNone(model)
        self.assertIn('无法确认',note)

    def test_explicit_body_and_header_metadata(self):
        for payload,headers in (({'model':'4p-akg-v8'},{}), ({},{'X-Model-ID':'4p-akg-v8'})):
            self.assertEqual(inference_model_report(payload,headers)[0],'4p-akg-v8')

    def test_conflicts_and_secrets_are_not_reported_as_models(self):
        self.assertIsNone(inference_model_report({'model':'4p-a'},{'X-Model-ID':'4p-b'})[0])
        self.assertIsNone(inference_model_report({'model':'offline-key'}, {},'offline-key')[0])
        self.assertIsNone(inference_model_report({'model':'<html>oops</html>'}, {})[0])

    def test_real_engine_callback_preserves_arrays_and_resets_missing_report(self):
        engine = MortalEngineAkagiOt('offline-key','http://legacy.example.invalid')
        self.addCleanup(engine.session.close)
        arrays = {'actions':[0],'q_out':[[1]],'masks':[[True]],'is_greedy':[True]}
        replies = [response(body=dict(arrays,model='4p-akg-v8')),response(body=arrays)]
        obs,masks = [np.zeros((2,2))],[np.ones(2,dtype=bool)]
        with patch.object(engine.session,'post',side_effect=replies):
            result = engine.react_batch(obs,masks,None)
            self.assertEqual(result,tuple(arrays.values()))
            self.assertTrue(engine.model_confirmed)
            bot = BotAkagiOt.__new__(BotAkagiOt)
            bot.name = 'legacy-test'
            bot.active_engine = engine
            self.assertEqual(bot.last_served_model,'4p-akg-v8')
            self.assertIn('4p-akg-v8',bot.info_str)
            engine.react_batch(obs,masks,None)
            self.assertFalse(bot.model_confirmed)
            self.assertIsNone(bot.last_served_model)


if __name__=='__main__':
    unittest.main()
