"""Owned-process and certificate boundaries, without executing a game."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from game.riichicity.tools import NativeTools


class ToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Offline fixture CA')])
        cls.cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(cls.key.public_key()).serial_number(1).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(cls.key,hashes.SHA256()).public_bytes(serialization.Encoding.PEM)

    def test_disabled_unlock_does_not_launch_any_external_program(self):
        native=NativeTools()
        values=SimpleNamespace(riichicity_unlock_enabled=False,riichicity_upstream_proxy='')
        with patch('game.riichicity.tools.subprocess.Popen') as spawn:
            self.assertEqual(native.route(values),('',None))
        spawn.assert_not_called()

    def test_port_collision_does_not_attach_to_or_stop_an_unowned_listener(self):
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/'unlock.exe'; exe.touch()
            native=NativeTools(trust_folder=directory)
            with patch.object(native,'listening',return_value=True),patch('game.riichicity.tools.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(ValueError,'占用'): native.ensure_unlock(str(exe))
            spawn.assert_not_called(); self.assertIsNone(native.unlock_process)

    def test_same_port_is_rejected_before_launch(self):
        native=NativeTools()
        with patch.object(native,'ensure_unlock') as start:
            with self.assertRaisesRegex(ValueError,'相同'):
                native.route(SimpleNamespace(riichicity_unlock_enabled=True,mitm_port=41110))
        start.assert_not_called()

    def test_trust_bundle_contains_public_roots_and_local_certificate_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); ca=root/'public.pem'; ca.write_bytes(self.cert)
            native=NativeTools(trust_folder=root/'trust')
            values=SimpleNamespace(riichicity_unlock_enabled=True,mitm_port=10999,
                riichicity_unlock_path='fixture.exe',riichicity_unlock_ca=str(ca))
            with patch.object(native,'ensure_unlock'):
                route,bundle=native.route(values)
            self.assertEqual(route,'http://127.0.0.1:41110')
            body=Path(bundle).read_bytes()
            self.assertIn(self.cert,body)
            self.assertGreater(body.count(b'BEGIN CERTIFICATE'),2)
            self.assertNotIn(b'PRIVATE KEY',body)

    def test_private_key_file_is_never_added_to_upstream_trust(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); ca=root/'private.pem'
            ca.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            native=NativeTools(trust_folder=root/'trust')
            values=SimpleNamespace(riichicity_unlock_enabled=True,mitm_port=10999,
                riichicity_unlock_path='fixture.exe',riichicity_unlock_ca=str(ca))
            with patch.object(native,'ensure_unlock'):
                with self.assertRaisesRegex(ValueError,'私钥'): native.route(values)
            self.assertFalse((root/'trust').exists())

    def test_injection_launch_only_targets_the_owned_executable_and_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'Native Game.exe'; exe.touch()
            helper=root/'proxinjector-cli.exe'; helper.touch(); (root/'proxinjectee.dll').touch()
            native=NativeTools(trust_folder=root/'trust')
            with patch('game.riichicity.capture.ConnectBridge') as bridge,patch('game.riichicity.tools.subprocess.Popen') as spawn:
                bridge.return_value.start.return_value=12345
                native.start_client(str(exe),injector=str(helper),proxy_port=10999)
            command=spawn.call_args.args[0]
            self.assertEqual(command,[str(helper),'--exec',subprocess.list2cmdline([str(exe)]),'--set-proxy','127.0.0.1:12345','--subprocess'])
            self.assertNotIn('--name',command)
            self.assertNotIn('shell',spawn.call_args.kwargs)

    def test_missing_injection_dll_does_not_launch_an_unproxied_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'game.exe'; exe.touch(); helper=root/'tool.exe'; helper.touch()
            native=NativeTools(trust_folder=root/'trust')
            with patch('game.riichicity.tools.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(ValueError,'dll'): native.start_client(str(exe),injector=str(helper),proxy_port=10999)
            spawn.assert_not_called()

    def test_stop_terminates_only_the_owned_unlock_process(self):
        native=NativeTools(); process=MagicMock(); process.poll.return_value=None
        native.unlock_process=process
        native.stop_unlock()
        process.terminate.assert_called_once(); process.kill.assert_not_called()
        self.assertIsNone(native.unlock_process)


if __name__=='__main__': unittest.main()
