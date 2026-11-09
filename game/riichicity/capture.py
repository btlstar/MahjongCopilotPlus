# MahjongCopilotPlus, 2026-11-05; see NOTICE.md.
"""Loopback SOCKS5 -> Copilot HTTP CONNECT for an owned native client.

Only TCP CONNECT is supported. Local IPC bypasses the proxy; this bridge never
changes the Windows proxy, routes or other processes.
"""
import asyncio
import ipaddress
import threading


class ConnectBridge:
    def __init__(self,proxy_port):
        self.proxy_port=proxy_port
        self.port=None
        self.ready=threading.Event()
        self.thread=None
        self.loop=None
        self.server=None
        self.tasks=set()
        self.error=None

    def start(self):
        if self.thread and self.thread.is_alive(): return self.port
        self.ready.clear()
        self.thread=threading.Thread(target=self.run,name='NativeCapture',daemon=True)
        self.thread.start()
        if not self.ready.wait(5) or self.error:
            raise ValueError('一番街本地捕获入口启动失败。')
        return self.port

    def run(self):
        self.loop=asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.server=self.loop.run_until_complete(asyncio.start_server(self.handle,'127.0.0.1',0,limit=65536))
            self.port=self.server.sockets[0].getsockname()[1]
            self.ready.set()
            self.loop.run_forever()
        except Exception as error:
            self.error=type(error).__name__
            self.ready.set()
        finally:
            if self.server:
                self.server.close()
                self.loop.run_until_complete(self.server.wait_closed())
            for task in tuple(self.tasks): task.cancel()
            if self.tasks: self.loop.run_until_complete(asyncio.gather(*tuple(self.tasks),return_exceptions=True))
            self.loop.close()

    @staticmethod
    def local(host):
        if host.lower()=='localhost' or host.lower().endswith('.localhost'): return True
        try:
            address=ipaddress.ip_address(host)
            return address.is_loopback or bool(getattr(address,'ipv4_mapped',None) and address.ipv4_mapped.is_loopback)
        except ValueError: return False

    async def handle(self,reader,writer):
        task=asyncio.current_task(); self.tasks.add(task)
        upstream=None
        replied=False
        pipes=[]
        try:
            head=await asyncio.wait_for(reader.readexactly(2),8)
            if head[0]!=5 or not 1<=head[1]<=32: return
            methods=await asyncio.wait_for(reader.readexactly(head[1]),8)
            writer.write(b'\x05\x00' if 0 in methods else b'\x05\xff'); await writer.drain()
            if 0 not in methods: return
            version,command,reserved,kind=await asyncio.wait_for(reader.readexactly(4),8)
            if version!=5 or command!=1 or reserved!=0: raise ValueError('unsupported SOCKS command')
            if kind==1:
                host=str(ipaddress.IPv4Address(await reader.readexactly(4)))
            elif kind==4:
                host=str(ipaddress.IPv6Address(await reader.readexactly(16)))
            elif kind==3:
                length=(await reader.readexactly(1))[0]
                if not length: raise ValueError('empty domain')
                host=(await reader.readexactly(length)).decode('ascii')
                if any(ord(c)<33 or c in ':/[]' for c in host): raise ValueError('invalid domain')
            else: raise ValueError('unsupported address')
            port=int.from_bytes(await reader.readexactly(2),'big')
            if not 1<=port<=65535: raise ValueError('invalid port')
            if self.local(host):
                if port in (self.proxy_port,self.port,41110): raise ValueError('proxy loop')
                remote,upstream=await asyncio.wait_for(asyncio.open_connection(host,port),8)
            else:
                remote,upstream=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',self.proxy_port),8)
                authority=('['+host+']' if ':' in host else host)+':'+str(port)
                upstream.write(f'CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n'.encode('ascii'))
                await upstream.drain()
                response=await asyncio.wait_for(remote.readuntil(b'\r\n\r\n'),8)
                if response.split(b'\r\n',1)[0].split()[1:2]!=[b'200']:
                    raise ValueError('HTTP CONNECT rejected')
            writer.write(b'\x05\x00\x00\x01'+bytes(6)); await writer.drain()
            replied=True
            async def pipe(source,destination):
                while True:
                    chunk=await source.read(65536)
                    if not chunk:
                        if destination.can_write_eof(): destination.write_eof()
                        return
                    destination.write(chunk); await destination.drain()
            pipes=[asyncio.create_task(pipe(reader,upstream)),asyncio.create_task(pipe(remote,writer))]
            await asyncio.gather(*pipes)
        except (OSError,ValueError,IndexError,UnicodeError,asyncio.IncompleteReadError,asyncio.LimitOverrunError,asyncio.TimeoutError):
            if not replied and not writer.is_closing():
                try:
                    writer.write(b'\x05\x01\x00\x01'+bytes(6)); await writer.drain()
                except OSError: pass
        finally:
            for job in pipes:
                if not job.done(): job.cancel()
            if pipes: await asyncio.gather(*pipes,return_exceptions=True)
            for stream in (writer,upstream):
                if stream:
                    stream.close()
                    try: await asyncio.wait_for(stream.wait_closed(),1)
                    except (OSError,asyncio.TimeoutError): pass
            self.tasks.discard(task)

    def stop(self):
        if self.loop and self.thread and self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=5)
