# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Differentiate catalog lookup, draft validation and completed client loading."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bot_manager import BotManager
from gui.preferences import test_ai_connection
from gui.ai_feedback import runtime_models_text


def values():
    return {'model_type':'AkagiOT','akagi_ot_protocol':'v3',
            'akagi_v3_url':'https://offline.invalid','akagi_v3_apikey':'offline-key',
            'akagi_v3_model_4p':'4p-selected','akagi_v3_model_3p':'3p-selected'}


class FeedbackTests(unittest.TestCase):
    def test_fetch_instructs_selection_without_validating_old_selection(self):
        choices = [{'id':'4p-new','game':'4p'},{'id':'3p-new','game':'3p'}]
        with patch('bot.akagiot.v3.AkagiV3Client.catalog',return_value=choices):
            result = test_ai_connection(values(),fetch_only=True)
        self.assertEqual(result['ot_models'],choices)
        self.assertIn('上方下拉框选择',result['message'])
        self.assertIn('保存配置',result['message'])
        self.assertNotIn('检查通过',result['message'])

    def test_connection_validates_selection_with_concise_feedback(self):
        choices = [{'id':'4p-selected','game':'4p'},{'id':'3p-selected','game':'3p'}]
        with patch('bot.akagiot.v3.AkagiV3Client.catalog',return_value=choices):
            checked = test_ai_connection(values())
            fetched = test_ai_connection(values(),fetch_only=True)
        self.assertNotEqual(checked['message'],fetched['message'])
        self.assertEqual(checked['message'],'连接与授权检查通过，所选模型可用。')
        self.assertNotIn('ot_models',checked)

    def test_invalid_selection_still_fails_connection_test(self):
        with patch('bot.akagiot.v3.AkagiV3Client.catalog',return_value=[{'id':'4p-other','game':'4p'}]):
            with self.assertRaises(ValueError):
                test_ai_connection(values())

    def test_runtime_uses_loaded_bot_not_unsaved_draft(self):
        bot = SimpleNamespace(protocol='v3',models={'4p':'4p-active','3p':'3p-active'},
                              model_confirmed=True,last_served_model='4p-active')
        manager = SimpleNamespace(bot=bot,is_loading_bot=False,bot_need_update=True)
        text = runtime_models_text(manager)
        self.assertIn('4p-active',text)
        self.assertIn('新配置待切换',text)
        self.assertIn('最近一次推理回报：4p-active',text)
        self.assertNotIn('4p-selected',text)

    def test_defaults_are_not_presented_as_a_confirmed_inference_model(self):
        bot = SimpleNamespace(protocol='v3',models={'4p':'','3p':''},model_confirmed=False)
        text = runtime_models_text(SimpleNamespace(bot=bot,is_loading_bot=False,bot_need_update=False))
        self.assertIn('未配置',text)
        self.assertIn('尚无模型 ID',text)

    def test_loading_completion_and_failure_are_published(self):
        manager = BotManager.__new__(BotManager)
        manager.st = SimpleNamespace(model_type='AkagiOT')
        manager.bot_load_revision = 0
        bot = SimpleNamespace(name='offline',supported_modes=[])
        def create(settings):
            self.assertTrue(manager.is_loading_bot)
            self.assertEqual(manager.bot_load_revision,0)
            return bot
        with patch('bot_manager.get_bot',side_effect=create):
            manager._create_bot()
        self.assertEqual(manager.bot_load_revision,1)
        self.assertFalse(manager.is_loading_bot)
        self.assertIs(manager.bot,bot)
        self.assertIsNone(manager.bot_load_error)
        with patch('bot_manager.get_bot',side_effect=ValueError('offline rejected')),patch('bot_manager.LOGGER.warning'):
            manager._create_bot()
        self.assertEqual(manager.bot_load_revision,2)
        self.assertFalse(manager.is_loading_bot)
        self.assertIsNone(manager.bot)
        self.assertEqual(str(manager.bot_load_error),'offline rejected')


if __name__=='__main__':
    unittest.main()
