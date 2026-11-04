# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Release inputs must not inherit live settings from a developer's machine."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common.settings import Settings
from common.log_helper import LOGGER
from mjmax import runtime
from gui import wardrobe

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('plus_builder',ROOT/'scripts/build_desktop.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PublicationTests(unittest.TestCase):
    def test_portable_defaults_never_copy_live_credentials_or_equipment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'source'
            config = root/'mjmax/config'
            config.mkdir(parents=True)
            for name in ('max_data.yaml','data_version.json','settings.example.yaml'):
                (config/name).write_text('public',encoding='utf-8')
            proto = root/'mjmax/proto'
            proto.mkdir()
            for name in ('liqi.desc','liqi.json'):
                (proto/name).write_text('public protocol',encoding='utf-8')
            (root/'resources').mkdir()
            (root/'resources/ui-check.svg').write_text('public icon',encoding='utf-8')
            (config/'settings.yaml').write_text('private-canary-token',encoding='utf-8')
            (config/'settings.mod.yaml').write_text('private-canary-equipment',encoding='utf-8')
            (root/'settings.json').write_text('private-canary-apikey',encoding='utf-8')
            (root/'settings.example.json').write_text('{"akagi_ot_apikey":"","akagi_v3_apikey":""}',encoding='utf-8')
            for name in ('version','LICENSE','NOTICE.md','THIRD_PARTY_NOTICES.md','readme.md'):
                (root/name).write_text('public',encoding='utf-8')
            (root/'LICENSES').mkdir()
            (root/'LICENSES/AGPL-3.0.txt').write_text('public',encoding='utf-8')
            (root/'proxinject').mkdir()
            (root/'proxinject/LICENSE').write_text('public',encoding='utf-8')
            package = Path(directory)/'package'
            package.mkdir()
            with patch.object(builder,'ROOT',root):
                builder.copy_public_defaults(package)
            self.assertFalse((package/'mjmax/config/settings.mod.yaml').exists())
            self.assertTrue((package/'mjmax/proto/liqi.desc').is_file())
            self.assertTrue((package/'mjmax/proto/liqi.json').is_file())
            self.assertTrue((package/'resources/ui-check.svg').is_file())
            for path in package.rglob('*'):
                if path.is_file():
                    self.assertNotIn('private-canary',path.read_text(encoding='utf-8'))

    def test_example_plugin_defaults_and_private_override_agree_with_gui(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'settings.example.yaml').write_text('plugin_enable:\n  mod: true\n',encoding='utf-8')
            with patch.object(runtime,'CONFIG',root),patch.object(wardrobe,'CONFIG',root):
                self.assertTrue(runtime.load_settings()['plugin_enable']['mod'])
                self.assertTrue(wardrobe.expansion_enabled())
                (root/'settings.yaml').write_text('plugin_enable:\n  mod: false\n',encoding='utf-8')
                self.assertFalse(runtime.load_settings()['plugin_enable']['mod'])
                self.assertFalse(wardrobe.expansion_enabled())

    def test_first_start_uses_public_example_but_saves_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'settings.example.json').write_text(json.dumps({'model_file':'','model_file_3p':'','akagi_ot_apikey':''}),encoding='utf-8')
            with patch('common.settings.utils.sub_file',side_effect=lambda folder,name:str(root/name)),patch.object(LOGGER,'warning'):
                settings = Settings()
            self.assertEqual(settings.model_file,'')
            self.assertEqual(json.loads((root/'settings.json').read_text(encoding='utf-8'))['akagi_ot_apikey'],'')


if __name__=='__main__':
    unittest.main()
