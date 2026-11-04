# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Network failures remain diagnosable without exposing request secrets."""
import queue
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mitm import WSDataInterceptor,WsType,network_error_summary,proxy_endpoint


class ProxyDiagnosticTests(unittest.TestCase):
    def test_refused_old_proxy_is_explained_without_exception_secrets(self):
        text = network_error_summary('[WinError 1225] http://user:private@127.0.0.1:7897/?token=private')
        self.assertIn('连接被拒绝',text)
        self.assertIn('1225',text)
        self.assertNotIn('private',text)
        self.assertIn('连接超时',network_error_summary('connection timed out'))
        self.assertIn('域名解析失败',network_error_summary('getaddrinfo failed'))
        self.assertIn('TLS',network_error_summary('certificate verify failed'))

    def test_proxy_route_does_not_display_credentials(self):
        self.assertEqual(proxy_endpoint('http://user:private@127.0.0.1:7897/path?secret=private'),
                         'http://127.0.0.1:7897')
        self.assertEqual(proxy_endpoint('http://[::1]:7897'),'http://[::1]:7897')
        self.assertEqual(proxy_endpoint('http://127.0.0.1:bad'),'代理地址无效')

    def test_http_failure_is_recorded_without_query_and_repeated_logs_are_limited(self):
        addon = WSDataInterceptor()
        flow = SimpleNamespace(request=SimpleNamespace(pretty_url='https://game.maj-soul.com/?token=private'),
                               error=SimpleNamespace(msg='[WinError 1225] private'))
        with patch('mitm.LOGGER.warning') as warning:
            addon.error(flow)
            addon.error(flow)
        self.assertEqual(warning.call_count,1)
        self.assertIn('game.maj-soul.com',addon.last_network_error)
        self.assertIn('1225',addon.last_network_error)
        self.assertNotIn('private',addon.last_network_error)

    def test_websocket_close_preserves_capture_event_and_records_close_metadata(self):
        addon = WSDataInterceptor(['maj-soul.com'])
        flow = SimpleNamespace(id='offline',timestamp_start=10,
            request=SimpleNamespace(pretty_url='wss://game.maj-soul.com/gateway?token=private'),
            websocket=SimpleNamespace(close_code=1006,closed_by_client=False,timestamp_end=70,
                                      close_reason='private payload'))
        with patch('mitm.LOGGER.info'):
            addon.websocket_end(flow)
        event = addon.message_queue.get_nowait()
        self.assertEqual((event.flow_id,event.type),('offline',WsType.END))
        with self.assertRaises(queue.Empty):
            addon.message_queue.get_nowait()
        self.assertIn('服务端关闭',addon.last_disconnect)
        self.assertIn('1006',addon.last_disconnect)
        self.assertIn('60 秒',addon.last_disconnect)
        self.assertNotIn('private',addon.last_disconnect)


if __name__=='__main__':
    unittest.main()
