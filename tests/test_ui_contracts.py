# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Regression checks for data/state boundaries introduced by the UI rebuild."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from common.settings import Settings
from common.lan_str import LanStrZHS
from common.presentation import action_tokens,advice_rows
from common.log_helper import LOGGER
from bot_manager import BotManager
from bot.akagiot.bot_akagiot import BotAkagiOt
from gui.wardrobe import save_expansion
from ruamel.yaml import YAML


class PresentationTests(unittest.TestCase):
    def test_normal_and_red_five_share_suit_but_keep_distinct_identity(self):
        lan = LanStrZHS()
        for code in ('5p','5pr'):
            row = action_tokens('切🀝'+lan.mjai2str(code),lan)
            tile = next(item['tile'] for item in row if 'tile' in item)
            self.assertEqual(tile['code'],code)
            self.assertEqual(tile['suit'],'筒')
            self.assertEqual(tile['red'],code.endswith('r'))

    def test_selected_lower_rank_has_its_own_probability(self):
        rows = advice_rows('切🀁南',[('🀌六萬',.67),('🀁南',.21),('🀃北',.08)],LanStrZHS())
        self.assertEqual([row['weight'] for row in rows],[.21,.67,.08])
        self.assertEqual(len(rows),3)

    def test_unmatched_action_does_not_claim_top_probability(self):
        rows = advice_rows('和牌',[('🀌六萬',.67)],LanStrZHS())
        self.assertIsNone(rows[0]['weight'])


class SettingsPersistenceTests(unittest.TestCase):
    def test_retired_floating_preferences_migrate_without_losing_other_settings(self):
        for game,floating,expected in ((True,False,True),(False,True,True),(False,False,False)):
            with self.subTest(game=game,floating=floating), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'settings.json'
                path.write_text(json.dumps({'enable_overlay':game,'show_floating_panel':floating,
                    'floating_opacity':80,'floating_topmost':True,'floating_geometry':[1,2,220,150],
                    'boss_key':'Alt+Z','future_option':7}),encoding='utf-8')
                with patch.object(LOGGER,'warning'):
                    settings = Settings(str(path))
                saved = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(settings.enable_overlay,expected)
                self.assertFalse(any('floating' in key for key in saved))
                self.assertEqual(saved['future_option'],7)
                self.assertEqual(saved['boss_key'],'Alt+Z')

    def test_migration_preserves_custom_hotkey_and_unknown_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            path.write_text(json.dumps({'boss_key':'Ctrl+Shift+F8','future_option':{'value':7}}),encoding='utf-8')
            with patch.object(LOGGER,'warning'):
                settings = Settings(str(path))
            self.assertEqual(settings.boss_key,'Ctrl+Shift+F8')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['future_option'],{'value':7})

    def test_failed_atomic_replace_keeps_original_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            with patch.object(LOGGER,'warning'):
                settings = Settings(str(path))
            original = path.read_bytes()
            settings.mitm_port = 11001
            with patch('common.settings.os.replace',side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    settings.save_json()
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_expansion_switch_preserves_user_equipment(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            path = config/'settings.yaml'
            path.write_text('plugin_enable:\n  mod: true\nliqi:\n  auto_update: false\n',encoding='utf-8')
            equipment = config/'settings.mod.yaml'
            equipment.write_text('config:\n  views_index: 1\n',encoding='utf-8')
            original = equipment.read_bytes()
            with patch('gui.wardrobe.CONFIG',config):
                save_expansion(False)
            result = YAML(typ='safe').load(path.read_text(encoding='utf-8'))
            self.assertFalse(result['plugin_enable']['mod'])
            self.assertFalse(result['liqi']['auto_update'])
            self.assertEqual(equipment.read_bytes(),original)


class ConnectionStateTests(unittest.TestCase):
    def test_akagi_failed_authorization_is_not_a_ready_bot(self):
        response = SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'result':'denied'})
        with patch('bot.akagiot.bot_akagiot.direct_session') as session:
            session.return_value.__enter__.return_value.post.return_value = response
            with self.assertRaises(ValueError):
                BotAkagiOt('https://example.invalid','offline-key')

    def test_new_request_during_loading_is_not_lost(self):
        manager = BotManager.__new__(BotManager)
        manager.bot_need_update = True
        manager.mitm_proxinject_need_update = False
        manager.is_in_game = lambda:False
        manager._create_bot = manager.set_bot_update
        manager._loop_pre_msg()
        self.assertTrue(manager.bot_need_update)


if __name__=='__main__':
    unittest.main()
