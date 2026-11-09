# MahjongCopilotPlus integration, 2026-11-05; see NOTICE.md.
"""Common AI/desktop adapter for Riichi City's read-only protocol bridge."""
from copy import deepcopy
import time
from common.mj_helper import GameInfo,sort_mjai_tiles
from common.utils import GameMode
from common.log_helper import LOGGER
from bot.bot import reaction_convert_meta
from .protocol import Bridge,decode_packets,ProtocolError


class RiichiCityState:
    def __init__(self,bot):
        self.mjai_bot=bot
        self.bridge=Bridge()
        self.game_mode=None
        self.seat=None
        self.info=None
        self.pending=[]
        self.bot_ready=False
        self.is_game_ended=False
        self.is_round_started=False
        self.is_ms_syncing=False
        self.is_bot_calculating=False
        self.last_error=None
        self.last_reaction=None
        self.last_reaction_pending=False
        self.last_reaction_time=None
        self.last_op_step=0
        self.own_discards=0
        self.desynced=False

    def get_game_info(self): return self.info

    def get_pending_reaction(self):
        return self.last_reaction if self.last_reaction_pending else None

    def input(self,content,from_client=None):
        self.is_bot_calculating=True
        started=time.monotonic()
        reaction=None
        try:
            packets=decode_packets(content)
            for packet in packets:
                command=packet.body.get('cmd','')
                if self.desynced and packet.command!=1 and command not in ('cmd_enter_room','cmd_game_start','cmd_room_end'):
                    continue
                events=self.bridge.feed(packet,from_client)
                cmd=self.bridge.last_command
                if events or cmd in ('cmd_game_action_brc','cmd_game_end','cmd_room_end'):
                    reaction=None
                    self.last_reaction_pending=False
                    self.last_op_step+=1
                for event in events:
                    self.apply_event(event)
                    self.pending.append(event)
                if self.bridge.decision and self.pending and self.bridge.live:
                    reaction=self.infer()
                if cmd in ('cmd_game_end','cmd_room_end'):
                    reaction=None
            if reaction is not None:
                self.last_reaction=reaction
                self.last_reaction_pending=True
                self.last_reaction_time=time.monotonic()-started
            return reaction
        except Exception as error:
            self.last_error=str(error)
            self.last_reaction_pending=False
            self.desynced=True
            self.pending=[]
            LOGGER.warning('Riichi City input failed: %s',type(error).__name__)
            return None
        finally:
            self.is_bot_calculating=False

    def infer(self):
        try:
            if self.mjai_bot is None: raise ValueError('请先配置并加载 AI。')
            if not self.bot_ready:
                self.mjai_bot.init_bot(self.seat,self.game_mode)
                self.bot_ready=True
            events=deepcopy(self.pending)
            if self.game_mode==GameMode.MJ3P:
                for event in events:
                    if event['type']=='start_game': event['names']=(event.get('names',[])+['']*4)[:4]
                    elif event['type']=='start_kyoku':
                        event['scores']=(event['scores']+[0]*4)[:4]
                        event['tehais']=(event['tehais']+[['?']*13 for _ in range(4)])[:4]
            self.pending=[]
            # The server's decision-window offer authorizes the final event,
            # even when a deferred dora follows its discard in the same frame.
            events[-1]['can_act']=True
            reaction=self.mjai_bot.react_batch(events)
            if reaction: reaction_convert_meta(reaction,self.game_mode==GameMode.MJ3P)
            self.last_error=None
            return reaction
        except Exception as error:
            self.last_error=str(error)
            self.last_reaction_pending=False
            LOGGER.warning('Riichi City inference failed: %s',type(error).__name__)
            return None

    def apply_event(self,event):
        kind=event['type']
        if kind=='start_game':
            self.game_mode=GameMode.MJ3P if self.bridge.count==3 else GameMode.MJ4P
            self.seat=event['id']
            self.bot_ready=False
            self.is_game_ended=False
            self.pending=[]
        elif kind=='start_kyoku':
            self.desynced=False
            self.own_discards=0
            self.is_round_started=True
            self.info=GameInfo(bakaze=event['bakaze'],jikaze='ESWN'[(self.seat-event['oya'])%self.bridge.count],
                kyoku=event['kyoku'],honba=event['honba'],my_tehai=sort_mjai_tiles(list(event['tehais'][self.seat])),
                my_tsumohai=None,self_reached=False,self_seat=self.seat,player_reached=[False]*4,is_first_round=True)
        elif kind=='end_game':
            self.is_game_ended=True
            self.last_reaction_pending=False
        elif self.info is not None:
            actor=event.get('actor')
            if kind=='reach':
                self.info.player_reached[actor]=True
                if actor==self.seat: self.info.self_reached=True
            if actor!=self.seat: return
            if kind=='tsumo': self.info.my_tsumohai=event['pai']
            elif kind in ('dahai','chi','pon','daiminkan','ankan','kakan','nukidora'):
                hand=list(self.info.my_tehai)
                if self.info.my_tsumohai: hand.append(self.info.my_tsumohai)
                consumed=event['consumed'] if kind in ('chi','pon','daiminkan','ankan') else [event['pai']]
                try:
                    for pai in consumed: hand.remove(pai)
                except ValueError:
                    raise ProtocolError('一番街手牌与动作不一致；未继续推理。') from None
                self.info.my_tehai=sort_mjai_tiles(hand)
                self.info.my_tsumohai=None
                if kind=='dahai':
                    self.own_discards+=1
                    self.info.is_first_round=False
