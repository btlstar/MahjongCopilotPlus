"""Synthetic native frames through protocol, state, manager and real local API."""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch,MagicMock

from bot.bot import Bot
from bot.akagiot.v3 import BotAkagiV3
from common.log_helper import LOGGER
from common.settings import Settings
from common.utils import GameMode
from game.riichicity.protocol import Bridge,ProtocolError,decode_packets,tile
from game.riichicity.state import RiichiCityState
from bot_manager import BotManager
from mitm import WSMessage,WsType
from test_akagi_v3 import Handler,MODEL_4P,MODEL_3P


def frame(command,data=None,*,binary=18,index=1,**extra):
    body={'cmd':command,'data':data or {},**extra} if command else extra
    payload=json.dumps(body).encode()
    return struct.pack('>IHHIHB',15+len(payload),15,1,index,binary,1)+payload


def room(count=4,token='offline-table'):
    return frame('cmd_enter_room',{'options':{'player_count':count},
        'players':[{'user':{'user_id':str(1001+i)}} for i in range(count)]},room_id=token)


def round_frame(count=4,dealer=0,me=0,honba=0,hand=None):
    cards=list(range(0x21,0x2a))+[1,2,3,4]
    if dealer==me: cards+=[5]
    return frame('cmd_game_start',{'quan_feng':0x31,'bao_pai_card':0x11,'dealer_pos':dealer,
        'ben_chang_num':honba,'li_zhi_bang_num':0,
        'user_info_list':[{'user_id':str(1001+i),'hand_points':21000+1000*i} for i in range(count)],
        'hand_cards':hand if hand is not None else cards})


def action(user,kind,card,**values):
    return frame('cmd_game_action_brc',{'action_info':[{'user_id':1001+user,'action':kind,'card':card,**values}]})


def start(state,count=4,dealer=0,me=0):
    state.input(frame('',binary=1,uid=str(1001+me)),True)
    state.input(room(count),False)
    return state.input(round_frame(count,dealer,me),False)


class RecordingBot(Bot):
    def __init__(self):
        super().__init__('offline recorder'); self.events=[]; self.decisions=0
    @property
    def supported_modes(self): return [GameMode.MJ4P,GameMode.MJ3P]
    def _init_bot_impl(self,mode): self.events=[]; self.mode=mode
    def react(self,message):
        self.events.append(deepcopy(message))
        if message.get('can_act'):
            self.decisions+=1
            return {'type':'dahai','actor':self.seat,'pai':'1m','meta_options':[('1m',1.0)]}


class PacketTests(unittest.TestCase):
    def test_big_endian_header_concatenation_and_exact_json(self):
        packets=decode_packets(frame('',binary=1,uid='1001')+room())
        self.assertEqual((packets[0].command,packets[0].body['uid']),(1,'1001'))
        self.assertEqual(packets[1].body['cmd'],'cmd_enter_room')
        self.assertEqual(decode_packets(b'not a native packet'),[])

    def test_invalid_trailing_packet_never_partially_decodes(self):
        raw=frame('',binary=1,uid='1001')
        for bad in (raw[:-1],raw+b'bad',raw[:14]+b'not json'):
            with self.subTest(kind=len(bad)),self.assertRaises(ProtocolError): decode_packets(bad)

    def test_all_suits_honors_red_and_unknown_tiles(self):
        for code,expected in ((1,'1p'),(0x19,'9s'),(0x21,'1m'),(0x31,'E'),(0x91,'C'),
                              (0x105,'5pr'),(0x115,'5sr'),(0x125,'5mr'),(0,'?')):
            self.assertEqual(tile(code),expected)
        for value in (0xff,1.5,True,None):
            with self.assertRaises(ProtocolError): tile(value)


class BridgeTests(unittest.TestCase):
    def bridge(self,count=4,dealer=0,me=0):
        bridge=Bridge()
        def send(raw,client=False):
            result=[]
            for packet in decode_packets(raw): result+=bridge.feed(packet,client)
            return result
        self.send=send
        send(frame('',binary=1,uid=str(1001+me)),True)
        send(room(count))
        events=send(round_frame(count,dealer,me))
        return bridge,events

    def test_rotated_seats_scores_and_own_hand_follow_the_same_actor(self):
        bridge,events=self.bridge(dealer=2,me=0)
        self.assertEqual(bridge.seat,2)
        self.assertEqual(events[0]['id'],2)
        self.assertEqual(events[1]['scores'],[23000,24000,21000,22000])
        self.assertEqual(events[1]['tehais'][0],['?']*13)
        self.assertNotEqual(events[1]['tehais'][2],['?']*13)
        self.assertEqual(events[-1],{'type':'tsumo','actor':0,'pai':'?'})

    def test_unknown_identity_never_defaults_to_seat_zero(self):
        bridge=Bridge()
        bridge.feed(decode_packets(room())[0],False)
        with self.assertRaises(ProtocolError): bridge.feed(decode_packets(round_frame())[0],False)
        self.assertIsNone(bridge.seat)

    def test_three_players_keep_native_actor_order_and_opening_draw(self):
        bridge,events=self.bridge(count=3,dealer=1,me=1)
        self.assertEqual(bridge.seat,0)
        self.assertEqual(len(events[1]['scores']),3)
        self.assertEqual(len(events[1]['tehais']),3)
        self.assertEqual(events[-1],{'type':'tsumo','actor':0,'pai':'5p'})

    def test_client_gameplay_injections_are_not_treated_as_server_notifications(self):
        bridge,_=self.bridge()
        self.assertEqual(self.send(round_frame(honba=2),True),[])
        self.assertTrue(bridge.started)

    def test_duplicate_opening_draw_is_not_added_twice(self):
        bridge,_=self.bridge()
        self.assertEqual(self.send(frame('cmd_send_current_action',{'in_card':5})),[])
        self.assertEqual(self.send(round_frame()),[])

    def test_red_pon_then_added_kan_preserves_actual_consumed_tiles(self):
        bridge,_=self.bridge()
        self.send(action(1,11,5,move_cards_pos=[14]))
        pon=self.send(action(2,5,5,group_cards=[0x105,5]))[-1]
        self.assertEqual(pon['consumed'],['5pr','5p'])
        kan=self.send(action(2,9,5))[-1]
        self.assertEqual(kan['consumed'],['5p','5pr','5p'])
        self.assertEqual(bridge.melds[2],1)

    def test_concealed_kan_uses_wire_red_instead_of_inventing_it(self):
        bridge,_=self.bridge()
        event=self.send(action(1,8,0x105,group_cards=[5,5,5]))[-1]
        self.assertEqual(event['consumed'],['5pr','5p','5p','5p'])
        with self.assertRaises(ProtocolError): self.send(action(2,8,5,group_cards=[]))

    def test_batched_actions_and_post_call_discard_are_not_tsumogiri(self):
        bridge,_=self.bridge()
        raw=frame('cmd_game_action_brc',{'action_info':[
            {'user_id':1002,'action':11,'card':5,'move_cards_pos':[14]},
            {'user_id':1003,'action':5,'card':5,'group_cards':[5,5]},
            {'user_id':1003,'action':11,'card':6,'move_cards_pos':[11]}]})
        events=self.send(raw)
        self.assertEqual([e['type'] for e in events],['dahai','pon','dahai'])
        self.assertFalse(events[-1]['tsumogiri'])

    def test_riichi_acceptance_and_kan_dora_order(self):
        bridge,_=self.bridge()
        self.send(frame('cmd_gang_bao_brc',{'cards':[0x21]}))
        events=self.send(action(1,11,5,is_li_zhi=True))
        self.assertEqual([e['type'] for e in events],['reach','dahai','dora'])
        following=self.send(frame('cmd_in_card_brc',{'user_id':1003,'card':9}))
        self.assertEqual([e['type'] for e in following],['reach_accepted','tsumo'])
        self.assertEqual(following[-1]['pai'],'?')

    def test_draw_settlement_with_tenpai_hand_reveal_is_not_a_win(self):
        bridge,_=self.bridge()
        events=self.send(frame('cmd_game_end',{'end_type':7,'win_info':[{'user_id':1001,'all_point':0}],
            'user_profit':[{'user_id':1001,'point_profit':1500}]}))
        self.assertEqual([e['type'] for e in events],['ryukyoku','end_kyoku'])
        self.assertEqual(events[0]['deltas'],[1500,0,0,0])

    def test_win_on_riichi_discard_does_not_deduct_unaccepted_stick(self):
        bridge,_=self.bridge()
        self.send(action(1,11,5,is_li_zhi=True))
        self.assertEqual(self.send(action(0,7,5)),[])
        events=self.send(frame('cmd_game_end',{'end_type':0,'win_info':[{'user_id':1001,'all_point':8000}]}))
        self.assertEqual([e['type'] for e in events],['hora','end_kyoku'])
        self.assertEqual(events[0]['target'],1)


class StateTests(unittest.TestCase):
    def test_dealer_first_decision_and_no_duplicate_prompt_inference(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        self.assertEqual(start(state)['type'],'dahai')
        self.assertEqual(bot.decisions,1)
        state.input(frame('cmd_send_current_action',{'in_card':5}),False)
        self.assertEqual(bot.decisions,1)
        self.assertEqual(state.get_game_info().my_tsumohai,'5p')
        self.assertEqual(len(state.get_game_info().my_tehai),13)

    def test_dealer_thirteenth_card_packet_waits_for_revealed_opening_draw(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        state.input(frame('',binary=1,uid='1001'),True); state.input(room(),False)
        state.input(round_frame(hand=list(range(0x21,0x2a))+[1,2,3,4]),False)
        self.assertEqual(bot.decisions,0)
        state.input(frame('cmd_send_current_action',{'in_card':5}),False)
        self.assertEqual(bot.decisions,1)
        self.assertEqual([e['type'] for e in bot.events],['start_game','start_kyoku','tsumo'])
        self.assertEqual(bot.events[-1]['pai'],'5p')

    def test_duplicate_opponent_opening_draw_is_not_fed_to_ai_twice(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        start(state,dealer=1)
        state.input(frame('cmd_in_card_brc',{'user_id':1002}),False)
        state.input(action(1,11,5),False)
        state.input(frame('cmd_send_other_action',{}),False)
        self.assertEqual(sum(e['type']=='tsumo' for e in bot.events),1)

    def test_other_discard_waits_for_server_offer_instead_of_wasting_requests(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        start(state,dealer=1)
        state.input(action(1,11,5),False)
        self.assertEqual(bot.decisions,0)
        state.input(frame('cmd_send_other_action',{}),False)
        self.assertEqual(bot.decisions,1)
        self.assertEqual(bot.events[-1]['type'],'dahai')

    def test_newer_action_in_same_frame_expires_preceding_recommendation(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        state.input(frame('',binary=1,uid='1001'),True)
        state.input(room(),False)
        self.assertIsNone(state.input(round_frame()+action(0,11,0x21),False))
        self.assertIsNone(state.get_pending_reaction())
        self.assertEqual(len(state.get_game_info().my_tehai),13)

    def test_bad_action_blocks_inference_until_next_round_and_recovers_flag(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        start(state)
        with patch.object(LOGGER,'warning'):
            state.input(action(0,11,0x91),False)
        self.assertTrue(state.desynced)
        self.assertFalse(state.is_bot_calculating)
        self.assertIsNone(state.get_pending_reaction())
        state.input(frame('cmd_send_other_action',{}),False)
        self.assertEqual(bot.decisions,1)
        state.input(round_frame(honba=1),False)
        self.assertFalse(state.desynced)
        self.assertEqual(bot.decisions,2)

    def test_sanma_north_extraction_updates_hand_and_normalizes_backend_width(self):
        bot=RecordingBot(); state=RiichiCityState(bot)
        state.input(frame('',binary=1,uid='1001'),True); state.input(room(3),False)
        hand=list(range(0x21,0x2a))+[1,2,3,4,0x61]
        state.input(round_frame(3,hand=hand),False)
        first=next(e for e in bot.events if e['type']=='start_kyoku')
        self.assertEqual(len(first['tehais']),4)
        self.assertEqual(first['scores'][-1],0)
        state.input(action(0,13,0x61),False)
        self.assertEqual(len(state.get_game_info().my_tehai),13)
        self.assertIsNone(state.get_game_info().my_tsumohai)
        self.assertEqual(bot.mode,GameMode.MJ3P)

    def test_manager_routes_native_frames_without_running_majsoul_automation(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(LOGGER,'warning'):
            settings=Settings(str(Path(directory)/'settings.json')); settings.platform='riichicity'
            manager=BotManager(settings); manager.bot=RecordingBot()
            manager.automation.automate_action=MagicMock()
            for raw,client in ((frame('',binary=1,uid='1001'),True),(room(),False),(round_frame(),False)):
                manager._process_msg(WSMessage('native',content=raw,from_client=client))
            self.assertEqual(manager.get_pending_reaction()['type'],'dahai')
            original=manager.game_state
            manager._process_msg(WSMessage('other',content=frame('',binary=1,uid='1002'),from_client=True))
            self.assertIs(manager.game_state,original)
            self.assertNotIn('other',manager.rc_flows)
            manager.automation.automate_action.assert_not_called()
            manager._process_msg(WSMessage('native',type=WsType.END))
            self.assertIsNone(manager.game_state)


    def test_native_lobby_connection_is_visible_before_a_match_and_clears_on_close(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(LOGGER,'warning'):
            settings=Settings(str(Path(directory)/'settings.json')); settings.platform='riichicity'
            manager=BotManager(settings)
            manager._process_msg(WSMessage('lobby',content=frame('',binary=1,uid='1001'),from_client=True))
            self.assertIsNotNone(manager.get_game_client_type())
            self.assertFalse(manager.is_in_game())
            manager._process_msg(WSMessage('lobby',type=WsType.END))
            self.assertIsNone(manager.get_game_client_type())

    def test_native_launch_rejects_unready_proxy_before_running_client(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(LOGGER,'warning'):
            settings=Settings(str(Path(directory)/'settings.json')); settings.platform='riichicity'
            manager=BotManager(settings)
            with patch.object(manager.native_tools,'start_client') as start_client:
                manager.connection_setup_error=ValueError('fixture startup failure')
                with self.assertRaisesRegex(ValueError,'fixture startup failure'): manager.start_browser()
                manager.connection_setup_error=None
                with self.assertRaisesRegex(ValueError,'尚未就绪'): manager.start_browser()
                start_client.assert_not_called()


class NativeApiTests(unittest.TestCase):
    def test_native_4p_and_3p_frames_reach_selected_model_and_verified_advice(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.calls,server.replies=[],[]
        worker=threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        try:
            for count,model in ((4,MODEL_4P),(3,MODEL_3P)):
                bot=BotAkagiV3(f'http://127.0.0.1:{server.server_port}','offline-key',MODEL_4P,MODEL_3P)
                try:
                    state=RiichiCityState(bot)
                    self.assertEqual(start(state,count=count)['pai'],'1m')
                    self.assertTrue(bot.model_confirmed)
                    self.assertEqual(bot.last_served_model,model)
                    payload=[c[3] for c in server.calls if c[0]=='POST'][-1]
                    self.assertEqual(payload['model'],model)
                    self.assertNotIn('user_id',json.dumps(payload['events']))
                    self.assertEqual([e['type'] for e in payload['events']],['start_game','start_kyoku','tsumo'])
                    self.assertEqual(state.get_game_info().self_seat,0)
                finally: bot.client.session.close()
        finally:
            server.shutdown(); worker.join(timeout=2); server.server_close()


if __name__=='__main__': unittest.main()
