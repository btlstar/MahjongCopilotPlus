"""Optional real local-tool smoke tests. Never logs in or joins a game."""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import queue
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from game.riichicity.capture import ConnectBridge
from game.riichicity.tools import NativeTools
from test_riichicity_capture import Server,Proxy
from test_riichicity import frame
from mitm import MitmController,WsType


def injected_fixture(helper):
    proxy=Server(('127.0.0.1',0),Proxy); proxy.requests=[]
    worker=threading.Thread(target=proxy.serve_forever,daemon=True); worker.start()
    bridge=ConnectBridge(proxy.server_address[1]); bridge.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); result=folder/'result.json'
            fixture=folder/'fixture.py'
            fixture.write_text('import json,socket\nfrom pathlib import Path\n'
                'with socket.create_connection(("203.0.113.1",443),timeout=3) as client:\n'
                ' client.sendall(b"owned-native-fixture")\n'
                ' value=client.recv(100)==b"owned-native-fixture"\n'
                +f'Path({str(result)!r}).write_text(json.dumps({{"ok":value}}))\n',encoding='utf-8')
            command=subprocess.list2cmdline([sys.executable,str(fixture)])
            completed=subprocess.run([str(helper),'--exec',command,'--set-proxy',f'127.0.0.1:{bridge.port}','--subprocess'],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=15)
            assert completed.returncode==0 and result.is_file(), 'Owned proxy fixture did not complete'
            assert json.loads(result.read_text())['ok']
            assert any(b'CONNECT 203.0.113.1:443' in request for request in proxy.requests)
    finally:
        bridge.stop(); proxy.shutdown(); worker.join(timeout=2); proxy.server_close()
    return {'owned_process_injection':True,'external_network_used':False}


def read_frame(stream):
    def read(size):
        data=stream.read(size)
        if len(data)!=size: raise ValueError('Incomplete WebSocket fixture')
        return data
    head=read(2); size=head[1]&127
    if size==126: size=struct.unpack('>H',read(2))[0]
    elif size==127: size=struct.unpack('>Q',read(8))[0]
    mask=read(4) if head[1]&128 else None
    data=read(size)
    return bytes(value^mask[index%4] for index,value in enumerate(data)) if mask else data


def ws_frame(payload,masked=False):
    length=len(payload)
    header=bytes([0x82,(0x80 if masked else 0)+(length if length<126 else 126)])
    if length>=126: header+=struct.pack('>H',length)
    if not masked: return header+payload
    mask=b'test'
    return header+mask+bytes(value^mask[index%4] for index,value in enumerate(payload))


class Origin(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args): pass
    def do_GET(self):
        if self.headers.get('Upgrade','').lower()!='websocket':
            self.send_response(200); self.send_header('Content-Length','2'); self.end_headers(); self.wfile.write(b'ok'); return
        accept=base64.b64encode(hashlib.sha1((self.headers['Sec-WebSocket-Key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101); self.send_header('Upgrade','websocket'); self.send_header('Connection','Upgrade')
        self.send_header('Sec-WebSocket-Accept',accept); self.end_headers()
        payload=read_frame(self.rfile)
        self.wfile.write(ws_frame(payload)); self.wfile.flush()
        self.close_connection=True


def unlock_chain(executable,certificate):
    native=NativeTools()
    native.log_folder=Path(__file__).resolve().parent.parent/'build/native-transport'
    origin=ThreadingHTTPServer(('127.0.0.1',0),Origin)
    worker=threading.Thread(target=origin.serve_forever,daemon=True); worker.start()
    controller=None
    try:
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); native.trust_folder=folder/'trust'
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1',0)); port=reserve.getsockname()[1]
            settings=SimpleNamespace(riichicity_unlock_enabled=True,riichicity_unlock_path=str(executable),
                riichicity_unlock_ca=str(certificate),riichicity_upstream_proxy='',mitm_port=port)
            upstream,ca=native.route(settings)
            controller=MitmController(); controller.platform='riichicity'
            controller.mitm_config_folder=folder/'copilot-ca'; controller.mitm_config_folder.mkdir()
            controller.cert_file=controller.mitm_config_folder/'mitmproxy-ca-cert.cer'
            controller.trusted_upstream_ca=ca
            controller.start(port,'http',upstream)
            deadline=time.monotonic()+20
            while not NativeTools.listening(port):
                assert time.monotonic()<deadline, 'Local capture proxy startup timeout'
                time.sleep(.1)
            payload=frame('copilot_offline_probe',{'value':'native-transport'})
            with socket.create_connection(('127.0.0.1',port),timeout=8) as client:
                authority=f'127.0.0.1:{origin.server_port}'
                request=(f'GET http://{authority}/native HTTP/1.1\r\nHost: {authority}\r\n'
                    'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n')
                client.sendall(request.encode())
                with client.makefile('rb') as stream:
                    status=stream.readline()
                    assert b'101' in status, 'Local WebSocket upgrade failed'
                    while stream.readline()!=b'\r\n': pass
                    client.sendall(ws_frame(payload,True))
                    assert read_frame(stream)==payload, 'Upstream unlock changed the probe frame'
            directions=[]
            deadline=time.monotonic()+5
            while len(directions)<2 and time.monotonic()<deadline:
                try: message=controller.get_message()
                except queue.Empty:
                    time.sleep(.05); continue
                if message.type==WsType.MESSAGE and message.content==payload: directions.append(message.from_client)
            assert sorted(directions)==[False,True], 'AI capture missed an original WebSocket direction'
            controller.stop(); controller=None
    finally:
        if controller: controller.stop()
        native.stop_unlock()
        origin.shutdown(); worker.join(timeout=2); origin.server_close()
    return {'external_unlock_http_chain':True,'websocket_bytes_preserved':True,'both_directions_captured':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--injector',type=Path)
    parser.add_argument('--unlock-exe',type=Path)
    parser.add_argument('--ca',type=Path,default=Path.home()/'.mitmproxy/mitmproxy-ca-cert.pem')
    options=parser.parse_args()
    results={}
    if options.injector: results.update(injected_fixture(options.injector))
    if options.unlock_exe: results.update(unlock_chain(options.unlock_exe,options.ca))
    assert results, 'Supply a local tool path to run its optional smoke test'
    print(json.dumps({'ok':True,**results}))


if __name__=='__main__': main()
