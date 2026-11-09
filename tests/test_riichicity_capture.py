"""Real socket checks for the native SOCKS5 -> HTTP CONNECT adapter."""
import socket
import socketserver
import struct
import threading
import unittest
from game.riichicity.capture import ConnectBridge


class Proxy(socketserver.BaseRequestHandler):
    def handle(self):
        data=b''
        while not data.endswith(b'\r\n\r\n'):
            chunk=self.request.recv(1)
            if not chunk: return
            data+=chunk
            if len(data)>65536: return
        self.server.requests.append(data)
        self.request.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
        while True:
            data=self.request.recv(4096)
            if not data: return
            self.request.sendall(data)


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        while True:
            data=self.request.recv(4096)
            if not data: return
            self.request.sendall(data)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.proxy=Server(('127.0.0.1',0),Proxy); self.proxy.requests=[]
        self.worker=threading.Thread(target=self.proxy.serve_forever,daemon=True); self.worker.start()
        self.bridge=ConnectBridge(self.proxy.server_address[1]); self.bridge.start()
        self.addCleanup(self.proxy.server_close)
        self.addCleanup(self.worker.join,2)
        self.addCleanup(self.proxy.shutdown)
        self.addCleanup(self.bridge.stop)

    def connect(self,host,port):
        client=socket.create_connection(('127.0.0.1',self.bridge.port),timeout=2)
        client.sendall(b'\x05\x01\x00'); self.assertEqual(client.recv(2),b'\x05\x00')
        try:
            address=socket.inet_pton(socket.AF_INET,host); kind=1
        except OSError:
            address=host.encode('ascii'); address=bytes([len(address)])+address; kind=3
        client.sendall(bytes([5,1,0,kind])+address+struct.pack('>H',port))
        response=b''
        while len(response)<10:
            chunk=client.recv(10-len(response))
            if not chunk: break
            response+=chunk
        return client,response

    def test_domain_tcp_uses_copilot_connect_and_preserves_payload(self):
        client,response=self.connect('game.fixture.test',443)
        try:
            self.assertEqual(response[:2],b'\x05\x00')
            client.sendall(b'opaque-native-frame')
            self.assertEqual(client.recv(100),b'opaque-native-frame')
            self.assertIn(b'CONNECT game.fixture.test:443 HTTP/1.1',self.proxy.requests[0])
        finally: client.close()

    def test_ipv4_remote_uses_connect_without_attempting_remote_connection(self):
        client,response=self.connect('203.0.113.1',80)
        try:
            self.assertEqual(response[:2],b'\x05\x00')
            self.assertIn(b'CONNECT 203.0.113.1:80',self.proxy.requests[0])
        finally: client.close()

    def test_loopback_ipc_goes_direct_instead_of_recursing_through_proxy(self):
        server=Server(('127.0.0.1',0),Echo)
        worker=threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        try:
            client,response=self.connect('127.0.0.1',server.server_address[1])
            try:
                self.assertEqual(response[:2],b'\x05\x00')
                client.sendall(b'local-ipc'); self.assertEqual(client.recv(100),b'local-ipc')
                self.assertEqual(self.proxy.requests,[])
            finally: client.close()
        finally: server.shutdown(); worker.join(timeout=2); server.server_close()

    def test_connect_to_capture_proxy_itself_is_rejected(self):
        client,response=self.connect('127.0.0.1',self.proxy.server_address[1])
        try: self.assertEqual(response[:2],b'\x05\x01')
        finally: client.close()

    def test_no_auth_is_required_and_other_auth_methods_are_rejected(self):
        with socket.create_connection(('127.0.0.1',self.bridge.port),timeout=2) as client:
            client.sendall(b'\x05\x01\x02')
            self.assertEqual(client.recv(2),b'\x05\xff')


if __name__=='__main__': unittest.main()
