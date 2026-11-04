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

from bot.akagiot.v3 import AkagiV3Client,BotAkagiV3,DEFAULT_4P,DEFAULT_3P,DEFAULT_URL
from common.settings import Settings
from common.log_helper import LOGGER
from common.utils import GameMode

CATALOG = [{'id':DEFAULT_4P,'game':'4p'},{'id':DEFAULT_3P,'game':'3p'}]


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
            body = {'model':body.get('model',DEFAULT_4P),
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

    def bot(self,mode=GameMode.MJ4P,seat=0,model4=DEFAULT_4P,model3=DEFAULT_3P):
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
        for mode,model in ((GameMode.MJ4P,DEFAULT_4P),(GameMode.MJ3P,DEFAULT_3P)):
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
            {'model':DEFAULT_4P,'reaction':{'type':'reach','actor':0}},
            {'model':DEFAULT_4P,'reaction':{'type':'dahai','actor':0,'pai':'2m','tsumogiri':True}}]
        reaction = bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertEqual(reaction['reach_dahai']['pai'],'2m')
        self.assertEqual(len(self.post_calls()),2)
        self.assertEqual(self.post_calls()[1][3]['events'][-1],{'type':'reach','actor':0})
        self.assertFalse(any(event['type']=='reach' for event in bot.events))
        bot.react({'type':'reach','actor':0})
        self.assertEqual(len(self.post_calls()),2)
        self.assertEqual(sum(event['type']=='reach' for event in bot.events),1)

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
        self.server.replies = [{'model':DEFAULT_4P,'reaction':{'type':'dahai','actor':1,'pai':'1m'}}]
        with self.assertRaisesRegex(ValueError,'其他座位'):
            bot.react({'type':'tsumo','actor':0,'pai':'2m'})

    def test_missing_model_report_does_not_claim_confirmation(self):
        bot = self.bot()
        self.server.replies = [{'reaction':{'type':'dahai','actor':0,'pai':'1m'}}]
        bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertFalse(bot.model_confirmed)
        self.assertIn('尚无推理确认',bot.info_str)

    def test_no_legal_action_can_still_confirm_served_model(self):
        bot = self.bot()
        self.server.replies = [{'model':DEFAULT_4P,'reaction':None}]
        self.assertIsNone(bot.react({'type':'dahai','actor':1,'pai':'2m','tsumogiri':True}))
        self.assertTrue(bot.model_confirmed)
        self.assertEqual(bot.last_served_model,DEFAULT_4P)

    def test_actual_majsoul_frames_reach_selected_model_and_advice_in_both_modes(self):
        from game.game_state import GameState
        from bot_manager import mjai_reaction_2_guide
        from common.lan_str import LanStrZHS
        from liqi import LiqiProto,MsgType
        from test_mjmax_integration import frame
        from mjmax.proto import liqi_pb2 as pb
        for count,model in ((4,DEFAULT_4P),(3,DEFAULT_3P)):
            with self.subTest(players=count), patch.dict('sys.modules',{'libriichi3p':None}):
                bot = BotAkagiV3(self.url,'offline-key')
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

    def test_default_model_omits_model_parameter(self):
        bot = self.bot(model4='')
        bot.react({'type':'tsumo','actor':0,'pai':'2m'})
        self.assertNotIn('model',self.post_calls()[-1][3])

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
