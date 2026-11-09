# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Real local HTTP contract checks for model selection, history and attribution."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from bot.akagiot.v3 import AkagiV3Client,BotAkagiV3,DEFAULT_URL
from common.settings import Settings
from common.log_helper import LOGGER
from common.utils import GameMode

MODEL_4P = '4p-fixture-selected'
MODEL_3P = '3p-fixture-selected'
CATALOG = [{'id':MODEL_4P,'game':'4p'},{'id':MODEL_3P,'game':'3p'}]


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def reply(self,body,status=200,kind='application/json'):
        raw = json.dumps(body).encode() if kind=='application/json' else body.encode()
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        self.server.calls.append(('GET',self.path,self.headers.get('Authorization'),None))
        self.reply({'models':CATALOG} if self.path=='/v3/models' else {'plan':'offline-test'})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append(('POST',self.path,self.headers.get('Authorization'),body))
        if self.server.replies:
            body = self.server.replies.pop(0)
        else:
            body = {'model':body.get('model',MODEL_4P),
                    'reaction':{'type':'dahai','actor':body['player_id'],'pai':'1m','tsumogiri':False},
                    'candidates':[{'action':'dahai:1m','prob':.73},{'action':'reach','prob':.21}]}
        self.reply(body)


class AkagiV3Tests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ,{'NO_PROXY':'127.0.0.1,localhost','no_proxy':'127.0.0.1,localhost'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.calls,self.server.replies = [],[]
        self.worker = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def bot(self,mode=GameMode.MJ4P,seat=0,model4=MODEL_4P,model3=MODEL_3P):
        bot = BotAkagiV3(self.url,'offline-key',model4,model3)
        self.addCleanup(bot.client.session.close)
        bot.init_bot(seat,mode)
        bot.react({'type':'start_game','id':seat})
        count = 3 if mode==GameMode.MJ3P else 4
        self.round(bot,count)
        return bot

    def round(self,bot,count):
        return bot.react({'type':'start_kyoku','bakaze':'E','dora_marker':'1s','kyoku':1,
            'honba':0,'kyotaku':0,'oya':bot.seat,'scores':[25000]*count,
            'tehais':[['1m']*13 if i==bot.seat else ['9m']*13 for i in range(count)]})

    def post_calls(self):
        return [entry for entry in self.server.calls if entry[0]=='POST']

    def test_each_mode_sends_requested_model_and_bearer_auth(self):
        for mode,model in ((GameMode.MJ4P,MODEL_4P),(GameMode.MJ3P,MODEL_3P)):
            with self.subTest(mode=mode):
                bot = self.bot(mode,seat=1)
                reaction = bot.react({'type':'tsumo','actor':1,'pai':'2m'})
                method,path,auth,body = self.post_calls()[-1]
                self.assertEqual((path,auth,body['model'],body['player_id']),('/v3/react','Bearer offline-key',model,1))
                self.assertNotIn('obs',body)
                self.assertEqual(reaction['meta_options'][0],('1m',.73))
                self.assertEqual(bot.last_served_model,model)
                self.assertTrue(bot.model_confirmed)

    def test_no_requests_for_history_or_non_decisions_and_opponents_are_censored(self):
        bot = self.bot(GameMode.MJ3P,seat=2)
        bot.react({'type':'tsumo','actor':2,'pai':'2m','can_act':False})
        bot.react({'type':'dahai','actor':2,'pai':'2m','tsumogiri':True,'can_act':False})
        bot.react({'type':'tsumo','actor':0,'pai':'9p'})
        self.assertEqual(self.post_calls(),[])
        bot.react({'type':'dahai','actor':0,'pai':'9p','tsumogiri':True})
        events = self.post_calls()[-1][3]['events']
        self.assertTrue(all('can_act' not in event for event in events))
        self.assertEqual(events[1]['scores'],[25000]*3+[0])
        self.assertEqual(events[1]['tehais'][0],['?']*13)
        self.assertEqual(events[1]['tehais'][3],['?']*13)
        self.assertEqual(events[-2]['pai'],'?')

    def test_next_round_drops_previous_round_history(self):
        bot = self.bot()
        bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.round(bot,4)
        bot.react({'type':'tsumo','actor':0,'pai':'3m'})
        events = self.post_calls()[-1][3]['events']
        self.assertEqual([event['type'] for event in events],['start_game','start_kyoku','tsumo'])
        self.assertEqual(events[-1]['pai'],'3m')

    def test_reach_gets_followup_without_duplicate_real_reach(self):
        bot = self.bot()
        self.server.replies = [
            {'model':MODEL_4P,'reaction':{'type':'reach','actor':0}},
            {'model':MODEL_4P,'reaction':{'type':'dahai','actor':0,'pai':'2m','tsumogiri':True}}]
        reaction = bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertEqual(reaction['reach_dahai']['pai'],'2m')
        self.assertEqual(len(self.post_calls()),2)
        self.assertEqual(self.post_calls()[1][3]['events'][-1],{'type':'reach','actor':0})
        self.assertFalse(any(event['type']=='reach' for event in bot.events))
        bot.react({'type':'reach','actor':0})
        self.assertEqual(len(self.post_calls()),2)
        self.assertEqual(sum(event['type']=='reach' for event in bot.events),1)

    def test_model_checks_cover_all_calls_and_riichi_followup(self):
        bot=self.bot()
        self.server.replies=[{'model':MODEL_4P,'reaction':{'type':'reach','actor':0}},
                             {'model':MODEL_4P,'reaction':{'type':'dahai','actor':0,'pai':'2m'}}]
        bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertEqual([r['phase'] for r in bot.model_checks],['decision','reach_discard'])
        self.assertEqual(bot.verified_total,2)
        self.assertEqual(bot.failed_total,0)
        self.assertTrue(all(r['requested']==r['served']==MODEL_4P for r in bot.model_checks))
        self.server.replies=[{'model':'4p-other','reaction':{'type':'dahai','actor':0,'pai':'1m'}}]
        with self.assertRaises(ValueError): bot.react({'type':'tsumo','actor':0,'pai':'3m'})
        self.assertEqual((bot.verified_total,bot.failed_total),(2,1))
        self.assertEqual(bot.last_model_check['status'],'mismatch')
        self.assertFalse(bot.model_confirmed)

    def test_riichi_followup_missing_model_rejects_the_whole_advice(self):
        bot=self.bot()
        self.server.replies=[{'model':MODEL_4P,'reaction':{'type':'reach','actor':0}},
                             {'reaction':{'type':'dahai','actor':0,'pai':'2m'}}]
        with self.assertRaisesRegex(ValueError,'未回报'):
            bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertFalse(bot.model_confirmed)
        self.assertEqual(bot.last_model_check['phase'],'reach_discard')
        self.assertEqual(bot.last_model_check['status'],'missing_model')

    def test_audit_is_bounded_and_does_not_log_credentials_or_events(self):
        bot=self.bot()
        reply={'model':MODEL_4P,'reaction':{'type':'dahai','actor':0,'pai':'1m'}}
        with patch.object(bot.client,'react',return_value=reply),self.assertLogs(LOGGER,level='INFO') as logs:
            for _ in range(35): bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertEqual(len(bot.model_checks),30)
        self.assertEqual(bot.verified_total,35)
        text='\n'.join(logs.output)
        self.assertNotIn('offline-key',text)
        self.assertNotIn('events',text)
        self.assertNotIn('pai',text)
        self.assertIn('requested='+MODEL_4P,text)
        self.assertIn('served='+MODEL_4P,text)
        self.assertEqual(bot.model_checks[0]['sequence'],6)

    def test_invalid_model_metadata_is_redacted_and_never_adopted(self):
        bot=self.bot()
        for value in ('offline-key','<html>error</html>','4p-bad\nheader'):
            self.server.replies=[{'model':value,'reaction':{'type':'none'}}]
            with self.assertLogs(LOGGER,level='INFO') as logs:
                with self.assertRaisesRegex(ValueError,'无效') as error:
                    bot.react({'type':'tsumo','actor':0,'pai':'2m'})
            self.assertNotIn(value,str(error.exception)+'\n'.join(logs.output))
            self.assertEqual(bot.last_model_check['status'],'invalid_model')
            self.assertIsNone(bot.last_model_check['served'])

    def test_friend_room_dealer_first_decision_each_round_and_after_failure(self):
        from game.game_state import GameState
        from liqi import MsgType,LiqiMethod,LiqiAction
        bot=self.bot()
        state=GameState(bot)
        state.account_id=123
        state.ms_auth_game({'seatList':[123,2,3,4],'gameConfig':{'meta':{'modeId':0}}})
        def new_round(honba):
            return {'type':MsgType.NOTIFY,'method':LiqiMethod.ActionPrototype,'data':{
                'name':LiqiAction.NewRound,'step':0,'data':{'chang':0,'ju':0,'ben':honba,
                'liqibang':0,'scores':[25000]*4,'doras':['1s'],
                'tiles':['1m','2m','3m','4m','5m','6m','7m','8m','9m','1p','2p','3p','1s','2s'],
                'operation':{'seat':0,'operationList':[{'type':1}]}}}}
        for honba in (0,1):
            reaction=state.input(new_round(honba))
            self.assertEqual(reaction['type'],'dahai')
            self.assertFalse(state.is_bot_calculating)
            events=self.post_calls()[-1][3]['events']
            self.assertEqual([e['type'] for e in events],['start_game','start_kyoku','tsumo'])
            self.assertEqual(events[1]['honba'],honba)
            self.assertEqual(self.post_calls()[-1][3]['model'],MODEL_4P)
        self.server.replies=[{'reaction':{'type':'dahai','actor':0,'pai':'1m'}}]
        with patch.object(LOGGER,'error'):
            self.assertIsNone(state.input(new_round(2)))
        self.assertFalse(state.is_bot_calculating)
        self.assertIn('未回报',state.last_error)
        self.assertIsNone(state.get_pending_reaction())
        self.assertEqual(state.input(new_round(3))['type'],'dahai')
        self.assertIsNone(state.last_error)
        self.assertEqual({entry[3]['model'] for entry in self.post_calls()},{MODEL_4P})

    def test_restart_uses_saved_models_and_running_client_ignores_draft_changes(self):
        from bot.factory import get_bot
        with tempfile.TemporaryDirectory() as directory,patch.object(LOGGER,'warning'):
            path=Path(directory)/'settings.json'
            settings=Settings(str(path))
            settings.model_type='AkagiOT'
            settings.akagi_ot_protocol='v3'
            settings.akagi_v3_url=self.url
            settings.akagi_v3_apikey='offline-key'
            settings.akagi_v3_model_4p=MODEL_4P
            settings.akagi_v3_model_3p=MODEL_3P
            settings.save_json()
            bot=get_bot(settings)
            self.addCleanup(bot.client.session.close)
            settings.akagi_v3_model_4p='4p-unsaved-draft'
            self.assertEqual(bot.models,{'4p':MODEL_4P,'3p':MODEL_3P})
            restarted=get_bot(Settings(str(path)))
            self.addCleanup(restarted.client.session.close)
            self.assertEqual(restarted.models,bot.models)
            restarted.init_bot(0,GameMode.MJ4P)
            restarted.react({'type':'start_game','id':0})
            self.round(restarted,4)
            restarted.react({'type':'tsumo','actor':0,'pai':'2m'})
            self.assertEqual(self.post_calls()[-1][3]['model'],MODEL_4P)
            self.assertEqual(restarted.last_served_model,MODEL_4P)

    def test_unavailable_model_does_not_fall_back_or_infer(self):
        with self.assertRaisesRegex(ValueError,'未改用其他模型'):
            BotAkagiV3(self.url,'offline-key',model_4p='4p-unknown')
        self.assertEqual(self.post_calls(),[])

    def test_different_returned_model_is_rejected(self):
        bot = self.bot()
        self.server.replies = [{'model':'4p-other','reaction':{'type':'dahai','actor':0,'pai':'1m'}}]
        with self.assertRaisesRegex(ValueError,'不符'):
            bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertFalse(bot.model_confirmed)
        self.assertIn('不符',bot.last_error)

    def test_other_seat_reaction_is_rejected(self):
        bot = self.bot()
        self.server.replies = [{'model':MODEL_4P,'reaction':{'type':'dahai','actor':1,'pai':'1m'}}]
        with self.assertRaisesRegex(ValueError,'其他座位'):
            bot.react({'type':'tsumo','actor':0,'pai':'2m'})

    def test_live_kita_response_is_normalized_for_sanma_advice(self):
        from bot_manager import mjai_reaction_2_guide
        bot = self.bot(mode=GameMode.MJ3P)
        self.server.replies = [{'model':MODEL_3P,'reaction':{'type':'kita','actor':0,'pai':'N'},
                                'candidates':[{'action':'nukidora','prob':.94}]}]
        reaction = bot.react({'type':'tsumo','actor':0,'pai':'N'})
        self.assertEqual(reaction['type'],'nukidora')
        self.assertEqual(reaction['pai'],'N')
        self.assertTrue(bot.model_confirmed)
        line,options = mjai_reaction_2_guide(reaction,3)
        self.assertIn('Nukidora',line)
        self.assertEqual(len(options),1)
        self.assertIn('Nukidora',options[0][0])
        self.assertEqual(options[0][1],.94)

    def test_kita_alias_does_not_bypass_other_seat_validation(self):
        bot = self.bot(mode=GameMode.MJ3P)
        self.server.replies = [{'model':MODEL_3P,'reaction':{'type':'kita','actor':1,'pai':'N'}}]
        with self.assertRaisesRegex(ValueError,'其他座位'):
            bot.react({'type':'tsumo','actor':0,'pai':'N'})

    def test_missing_model_report_is_rejected_without_confirmation(self):
        bot = self.bot()
        self.server.replies = [{'reaction':{'type':'dahai','actor':0,'pai':'1m'}}]
        with self.assertRaisesRegex(ValueError,'未回报'):
            bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertFalse(bot.model_confirmed)
        self.assertEqual(bot.last_model_check['status'],'missing_model')
        self.assertEqual(bot.failed_total,1)
        self.assertIn('尚无推理确认',bot.info_str)

    def test_no_legal_action_can_still_confirm_served_model(self):
        bot = self.bot()
        self.server.replies = [{'model':MODEL_4P,'reaction':None}]
        self.assertIsNone(bot.react({'type':'dahai','actor':1,'pai':'2m','tsumogiri':True}))
        self.assertTrue(bot.model_confirmed)
        self.assertEqual(bot.last_served_model,MODEL_4P)

    def test_actual_majsoul_frames_reach_selected_model_and_advice_in_both_modes(self):
        from game.game_state import GameState
        from bot_manager import mjai_reaction_2_guide
        from common.lan_str import LanStrZHS
        from liqi import LiqiProto,MsgType
        from test_mjmax_integration import frame
        from mjmax.proto import liqi_pb2 as pb
        for count,model in ((4,MODEL_4P),(3,MODEL_3P)):
            with self.subTest(players=count), patch.dict('sys.modules',{'libriichi3p':None}):
                bot = BotAkagiV3(self.url,'offline-key',MODEL_4P,MODEL_3P)
                self.addCleanup(bot.client.session.close)
                state,parser = GameState(bot),LiqiProto()
                with patch.object(LOGGER,'info'):
                    state.input(parser.parse(frame(2,'.lq.FastTest.authGame',pb.ReqAuthGame(account_id=123456))))
                    response = pb.ResAuthGame(seat_list=[123456]+list(range(2,count+1)))
                    response.game_config.meta.mode_id = 2
                    state.input(parser.parse(frame(3,'',response)))
                    raw = parser.compose_notify({'type':MsgType.NOTIFY,'method':'.lq.ActionPrototype',
                        'data':{'name':'ActionNewRound','step':0,'data':{'chang':0,'ju':0,
                            'tiles':['1m','9m','1p','2p','3p','4p','5p','6p','7p','8p','9p','1s','2s','3s'],
                            'doras':['1s'],'scores':[25000]*count,'sha256':'a'*64,
                            'operation':{'seat':0,'operationList':[{'type':1}]}}}})
                    reaction = state.input(parser.parse(raw))
                self.assertEqual(self.post_calls()[-1][3]['model'],model)
                self.assertEqual(reaction['meta_options'][0],('1m',.73))
                line,options = mjai_reaction_2_guide(reaction,3,LanStrZHS())
                self.assertIn('一萬',line)
                self.assertEqual(options[0][1],.73)
                self.assertEqual(state.get_pending_reaction(),reaction)

    def test_unconfigured_mode_is_not_available_and_does_not_infer(self):
        from common.utils import BotNotSupportingMode
        bot = self.bot(mode=GameMode.MJ3P,model4='')
        self.assertNotIn(GameMode.MJ4P,bot.supported_modes)
        with self.assertRaises(BotNotSupportingMode):
            bot.init_bot(0,GameMode.MJ4P)
        self.assertEqual(self.post_calls(),[])

    def test_empty_new_config_requires_manual_choice_before_network(self):
        with patch('bot.akagiot.v3.requests.Session.request') as request:
            with self.assertRaisesRegex(ValueError,'至少选择'):
                BotAkagiV3(self.url,'offline-key')
        request.assert_not_called()

    def test_settings_have_no_preset_but_retain_saved_choices(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(LOGGER,'warning'):
            path = Path(directory)/'settings.json'
            path.write_text('{}',encoding='utf-8')
            setting = Settings(str(path))
            self.assertEqual((setting.akagi_v3_model_4p,setting.akagi_v3_model_3p),('',''))
            path.write_text(json.dumps({'akagi_v3_model_4p':'4p-user-choice','akagi_v3_model_3p':'3p-user-choice'}),encoding='utf-8')
            setting = Settings(str(path))
            self.assertEqual((setting.akagi_v3_model_4p,setting.akagi_v3_model_3p),('4p-user-choice','3p-user-choice'))

    def test_legacy_credentials_are_not_reused_for_v3(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            path.write_text(json.dumps({'akagi_ot_url':'http://legacy.invalid','akagi_ot_apikey':'private-old-key'}),encoding='utf-8')
            with patch.object(LOGGER,'warning'):
                setting = Settings(str(path))
            self.assertEqual(setting.akagi_ot_protocol,'legacy')
            self.assertEqual(setting.akagi_v3_url,DEFAULT_URL)
            self.assertEqual(setting.akagi_v3_apikey,'')
            self.assertEqual(setting.akagi_ot_apikey,'private-old-key')


if __name__=='__main__':
    unittest.main()
