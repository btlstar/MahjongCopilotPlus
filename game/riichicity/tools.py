# MahjongCopilotPlus integration, 2026-11-05; see NOTICE.md.
"""Owned native client / separately supplied RiichiCityUnlock process."""
import os
import certifi
from cryptography import x509
from pathlib import Path
import socket
import subprocess
import time


class NativeTools:
    def __init__(self,trust_folder=None):
        self.trust_folder=Path(trust_folder) if trust_folder else Path(__file__).resolve().parents[2]/'mitm_config'
        self.unlock_process=None
        self.client_process=None
        self.unlock_path=None
        self.last_error=None
        self.capture_bridge=None
        self.log_folder=(Path(trust_folder)/'logs') if trust_folder else Path(__file__).resolve().parents[2]/'log'

    @staticmethod
    def find_client():
        appdata=os.environ.get('APPDATA','')
        path=Path(appdata)/'RiichicityLauncher/Game/Mahjong-JP.exe'
        return str(path) if appdata and path.is_file() else ''

    @staticmethod
    def listening(port):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2): return True
        except OSError: return False

    @staticmethod
    def executable(value):
        path=Path(value).expanduser() if value else None
        if path is None or not path.is_file() or path.suffix.lower()!='.exe':
            raise ValueError('请选择存在的 Windows exe 文件。')
        return path.resolve()

    def ensure_unlock(self,value,port=41110):
        path=self.executable(value)
        if self.unlock_process and self.unlock_process.poll() is None:
            if path!=self.unlock_path: raise ValueError('请先停用并关闭当前解锁工具，再切换文件路径。')
            return
        if self.listening(port):
            raise ValueError(f'一番街解锁端口 {port} 已被占用；请关闭单独运行的工具，再由 Copilot 启动。')
        self.log_folder.mkdir(parents=True,exist_ok=True)
        environment=dict(os.environ,PYTHONUNBUFFERED='1')
        with (self.log_folder/'riichicity-unlock.log').open('ab') as output:
            self.unlock_process=subprocess.Popen([str(path)],cwd=path.parent,
                stdout=output,stderr=output,env=environment,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.unlock_path=path
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if self.unlock_process.poll() is not None:
                raise ValueError('RiichiCityUnlock 已退出，请检查其本地配置或手动运行日志。')
            if self.listening(port): return
            time.sleep(.1)
        self.stop_unlock()
        raise ValueError('RiichiCityUnlock 未在 41110 端口就绪。')

    def route(self,settings):
        if not settings.riichicity_unlock_enabled:
            self.stop_unlock()
            return settings.riichicity_upstream_proxy,None
        if settings.mitm_port==41110:
            raise ValueError('Copilot 本地端口不能与 RiichiCityUnlock 的 41110 相同。')
        self.ensure_unlock(settings.riichicity_unlock_path)
        ca=Path(settings.riichicity_unlock_ca or Path.home()/'.mitmproxy/mitmproxy-ca-cert.pem')
        if not ca.is_file():
            self.stop_unlock()
            raise ValueError('未找到解锁工具 CA 证书；请在平台设置选择其 mitmproxy-ca-cert.pem。')
        certificate=ca.read_bytes()
        if len(certificate)>1024*1024 or b'PRIVATE KEY' in certificate:
            self.stop_unlock()
            raise ValueError('请选择不包含私钥的 CA 公共证书文件。')
        try:
            parsed=x509.load_pem_x509_certificate(certificate)
            if not parsed.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
                raise ValueError()
        except (ValueError,x509.ExtensionNotFound):
            self.stop_unlock()
            raise ValueError('解锁工具 CA 不是有效的 PEM 根证书。') from None
        # Preserve Mozilla roots as well as the local unlock CA, so domains
        # passed through without rewriting retain normal TLS verification.
        folder=self.trust_folder
        folder.mkdir(exist_ok=True)
        bundle=folder/'riichicity-upstream-ca.pem'
        pending=bundle.with_suffix('.pending')
        try:
            pending.write_bytes(Path(certifi.where()).read_bytes()+b'\n'+certificate)
            os.replace(pending,bundle)
        finally:
            pending.unlink(missing_ok=True)
        return 'http://127.0.0.1:41110',str(bundle)

    def start_client(self,value,*,injector='',proxy_port=None):
        path=self.executable(value or self.find_client())
        if self.client_process and self.client_process.poll() is None: return
        command=[str(path)]
        if injector:
            helper=self.executable(injector)
            if not (helper.parent/'proxinjectee.dll').is_file():
                raise ValueError('代理注入工具缺少同目录的 proxinjectee.dll，请保留完整工具目录。')
            from .capture import ConnectBridge
            self.stop_capture()
            self.capture_bridge=ConnectBridge(proxy_port)
            port=self.capture_bridge.start()
            # --exec creates and injects this client before its normal startup;
            # --subprocess affects only descendants of this owned game process.
            command=[str(helper),'--exec',subprocess.list2cmdline([str(path)]),
                     '--set-proxy',f'127.0.0.1:{port}','--subprocess']
        try:
            if injector:
                self.log_folder.mkdir(parents=True,exist_ok=True)
                with (self.log_folder/'riichicity-capture.log').open('ab') as output:
                    self.client_process=subprocess.Popen(command,cwd=path.parent,
                        stdout=output,stderr=output,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            else:
                self.client_process=subprocess.Popen(command,cwd=path.parent,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError:
            self.stop_capture()
            raise

    def stop_capture(self):
        if self.capture_bridge:
            self.capture_bridge.stop()
            self.capture_bridge=None

    def stop_unlock(self):
        process=self.unlock_process
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
        self.unlock_process=None
        self.unlock_path=None
