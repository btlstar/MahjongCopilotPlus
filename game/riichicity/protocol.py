# MahjongCopilotPlus integration, 2026-11-05.
# Protocol/state behavior adapted from Akagi v3, Copyright 2026 Shinkuan.
# See LICENSES/Akagi-NOTICE.txt and LICENSES/Apache-2.0.txt.
"""Read-only WPacket -> MJAI bridge. Never constructs gameplay requests."""
from dataclasses import dataclass
import json
import struct


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Packet:
    index: int
    command: int
    body: dict


def decode_packets(content):
    if not isinstance(content,bytes) or len(content)<15 or content[4:8]!=b'\x00\x0f\x00\x01':
        return []
    packets=[]
    offset=0
    while offset<len(content):
        if len(packets)>=128 or len(content)-offset<15:
            raise ProtocolError('一番街数据包不完整或数量异常。')
        size,header,version,index,command,flag=struct.unpack_from('>IHHIHB',content,offset)
        if header!=15 or version!=1 or not 15<=size<=16*1024*1024 or offset+size>len(content) or flag not in (0,1):
            raise ProtocolError('一番街数据包头或长度无效。')
        try:
            body=json.loads(content[offset+15:offset+size].decode('utf-8')) if size>15 else {}
        except (ValueError,UnicodeError):
            raise ProtocolError('一番街数据包不是有效 JSON。') from None
        if not isinstance(body,dict):
            raise ProtocolError('一番街数据包正文格式无效。')
        packets.append(Packet(index,command,body))
        offset+=size
    return packets


def integer(value):
    if isinstance(value,bool) or not isinstance(value,(int,str)):
        raise ProtocolError('一番街数值字段类型无效。')
    try: return int(value)
    except (ValueError,TypeError,OverflowError):
        raise ProtocolError('一番街缺少必要的数值字段。') from None


def tile(value):
    code=integer(value)
    if code==0: return '?'
    if code in (0x105,0x115,0x125): return {0x105:'5pr',0x115:'5sr',0x125:'5mr'}[code]
    if code in (0x31,0x41,0x51,0x61,0x71,0x81,0x91):
        return {0x31:'E',0x41:'S',0x51:'W',0x61:'N',0x71:'P',0x81:'F',0x91:'C'}[code]
    suit,rank=divmod(code,16)
    if suit in (0,1,2) and 1<=rank<=9: return str(rank)+'psm'[suit]
    raise ProtocolError('一番街出现未知牌编码，已停止采用本次建议。')


def known_tile(value):
    result=tile(value)
    if result=='?': raise ProtocolError('一番街动作缺少明确的牌。')
    return result


def flag(value):
    return value is True or value in (1,'1')


class Bridge:
    def __init__(self):
        self.uid=None
        self.players=[]
        self.room_id=None
        self.count=None
        self.seat=None
        self.shift=None
        self.started=False
        self.live=False
        self.decision=False
        self.last_command=''
        self.round_key=None
        self.last_actor=None
        self.drawn_by=None
        self.drawn_tile=None
        self.melds=[0]*4
        self.pons=[[] for _ in range(4)]
        self.pending_reach=None
        self.pending_dora=[]

    def actor(self,value):
        try: return self.players.index(integer(value))
        except ValueError: raise ProtocolError('一番街玩家不在当前座位表中。') from None

    def flush_reach(self):
        if self.pending_reach is None: return []
        actor=self.pending_reach
        self.pending_reach=None
        return [{'type':'reach_accepted','actor':actor}]

    def feed(self,packet,from_client=None):
        self.decision=False
        body=packet.body
        if packet.command==1 and from_client is not False:
            uid=integer(body.get('uid'))
            if self.started and self.uid!=uid: raise ProtocolError('一番街账号已变化，请重新进入牌局。')
            self.uid=uid
            return []
        if from_client is True: return []
        cmd=body.get('cmd','')
        self.last_command=cmd
        data=body.get('data') or {}
        if not isinstance(data,dict): raise ProtocolError('一番街通知数据格式无效。')
        if cmd=='cmd_enter_room':
            options=data.get('options') or {}
            count=integer(options.get('player_count',4))
            players=[integer(p['user']['user_id']) for p in data.get('players',[])]
            if count not in (3,4) or len(players)!=count or len(set(players))!=count:
                raise ProtocolError('一番街座位表不完整，暂不计算。')
            room=body.get('room_id')
            if self.started and room==self.room_id and set(players)==set(self.players): return []
            old=[{'type':'end_game'}] if self.started else []
            self.room_id,self.count,self.players=room,count,players
            self.started,self.shift,self.seat,self.live=False,None,None,False
            self.round_key=None
            return old
        if cmd=='cmd_game_start': return self.start_round(data)
        if cmd=='cmd_send_other_action':
            self.decision=True
            return []
        if cmd=='cmd_in_card_brc':
            if not self.started: return []
            actor=self.actor(data.get('user_id'))
            if actor==self.seat or self.drawn_by==actor: return [] # own revealed draw follows separately; suppress duplicate opening draw
            self.drawn_by,self.drawn_tile=actor,None
            return self.flush_reach()+[{'type':'tsumo','actor':actor,'pai':'?'}]
        if cmd=='cmd_send_current_action':
            if not self.started: return []
            self.decision=True
            pai=tile(data.get('in_card',0))
            if pai=='?': return self.flush_reach() # post-chi/pon discard prompt
            if self.drawn_by==self.seat and self.drawn_tile==pai: return []
            self.drawn_by,self.drawn_tile=self.seat,pai
            return self.flush_reach()+[{'type':'tsumo','actor':self.seat,'pai':pai}]
        if cmd=='cmd_game_action_brc': return self.actions(data)
        if cmd=='cmd_gang_bao_brc':
            cards=data.get('cards') or []
            if cards: self.pending_dora.append(known_tile(cards[-1]))
            return []
        if cmd=='cmd_game_end': return self.settlement(data)
        if cmd=='cmd_room_end':
            self.started,self.live=False,False
            return [{'type':'end_game'}]
        if cmd in ('cmd_game_reconnect','cmd_reconnect_game'):
            raise ProtocolError('一番街中途重连状态尚未恢复；请从下一小局开始验证。')
        return []

    def start_round(self,data):
        if not self.players or self.uid not in self.players:
            raise ProtocolError('未捕获一番街登录或完整座位表；请在代理接通后重新进入房间。')
        n=self.count
        dealer=integer(data.get('dealer_pos'))
        if not 0<=dealer<n: raise ProtocolError('一番街庄家座位无效。')
        events=[]
        if not self.started:
            self.players=self.players[dealer:]+self.players[:dealer]
            self.shift=dealer
            self.seat=self.players.index(self.uid)
            self.started=True
            events.append({'type':'start_game','id':self.seat,'names':['']*n})
        oya=(dealer-self.shift)%n
        scores=[None]*n
        for player in data.get('user_info_list',[]):
            scores[self.actor(player.get('user_id'))]=integer(player.get('hand_points'))
        if any(v is None for v in scores): raise ProtocolError('一番街分数与座位表不一致。')
        hand=[known_tile(c) for c in data.get('hand_cards',[])]
        if len(hand) not in (13,14) or (len(hand)==14 and oya!=self.seat):
            raise ProtocolError('一番街起手牌数量或庄家归属异常。')
        hands=[['?']*13 for _ in range(n)]
        hands[self.seat]=hand[:13]
        bakaze=known_tile(data.get('quan_feng'))
        if bakaze not in 'ESWN': raise ProtocolError('一番街场风无效。')
        round_key=(bakaze,dealer,integer(data.get('ben_chang_num',0)),integer(data.get('li_zhi_bang_num',0)),tuple(hand),tuple(scores))
        if self.live and round_key==self.round_key: return []
        self.round_key=round_key
        events.append({'type':'start_kyoku','bakaze':bakaze,'oya':oya,'kyoku':oya+1,
            'honba':integer(data.get('ben_chang_num',0)),
            'kyotaku':integer(data.get('li_zhi_bang_num',0)),
            'dora_marker':known_tile(data.get('bao_pai_card')),'scores':scores,'tehais':hands})
        own=len(hand)==14
        actor=self.seat if own else oya
        pai=hand[13] if own else '?'
        # Some clients deliver the dealer's 14th tile separately. Never send
        # a hidden own draw and then the revealed same draw to the AI.
        await_own_draw=oya==self.seat and not own
        if not await_own_draw:
            events.append({'type':'tsumo','actor':actor,'pai':pai})
        self.last_actor,self.pending_reach=None,None
        self.pending_dora=[]
        self.melds=[0]*n
        self.pons=[[] for _ in range(n)]
        self.drawn_by,self.drawn_tile=(None,None) if await_own_draw else (actor,pai if own else None)
        self.live,self.decision=True,own
        return events

    def actions(self,data):
        if not self.started: return []
        events=[]
        actions=data.get('action_info') or []
        if not isinstance(actions,list): raise ProtocolError('一番街动作列表无效。')
        for item in actions:
            action=integer(item.get('action'))
            if action in (0,1): continue
            if action in (7,10,12):
                self.decision=False
                continue
            # A ron notice can follow the declaration discard. Let settlement
            # reject that pending stick instead of accepting it prematurely.
            events.extend(self.flush_reach())
            actor=self.actor(item.get('user_id'))
            pai=known_tile(item.get('card'))
            group=[known_tile(c) for c in item.get('group_cards',[])]
            event={'actor':actor}
            if action in (2,3,4,5,6):
                expected=3 if action==6 else 2
                if len(group)!=expected: raise ProtocolError('一番街副露用牌不完整。')
                if self.last_actor is None or self.last_actor==actor:
                    raise ProtocolError('一番街副露缺少对应弃牌。')
                event.update(type='chi' if action in (2,3,4) else 'pon' if action==5 else 'daiminkan',
                             pai=pai,consumed=group,target=self.last_actor)
                self.melds[actor]+=1
                self.drawn_by,self.drawn_tile=None,None
                if action==5: self.pons[actor].append([pai]+group)
                self.decision=actor==self.seat and action!=6
            elif action==8:
                consumed=[pai]+group
                if len(consumed)!=4 or any(c.rstrip('r')!=pai.rstrip('r') for c in consumed) or sum(c.endswith('r') for c in consumed)>1:
                    raise ProtocolError('一番街暗杠用牌无效，未猜测赤牌。')
                event.update(type='ankan',consumed=consumed)
                self.melds[actor]+=1
                self.drawn_by,self.drawn_tile=None,None
            elif action==9:
                previous=next((p for p in self.pons[actor] if p[0].rstrip('r')==pai.rstrip('r')),None)
                if previous is None: raise ProtocolError('一番街加杠缺少此前的碰牌记录。')
                self.pons[actor].remove(previous)
                event.update(type='kakan',pai=pai,consumed=previous)
                self.drawn_by,self.drawn_tile=None,None
            elif action==11:
                if flag(item.get('is_li_zhi')):
                    events.append({'type':'reach','actor':actor})
                    self.pending_reach=actor
                positions=item.get('move_cards_pos') or []
                tsumogiri=self.drawn_by==actor and (not positions or integer(positions[0])==14-3*self.melds[actor])
                event.update(type='dahai',pai=pai,tsumogiri=tsumogiri)
                self.last_actor=actor
                self.drawn_by,self.drawn_tile=None,None
                self.decision=False # ask only when the server offers a response
            elif action==13:
                if pai!='N': raise ProtocolError('一番街拔北牌无效。')
                event.update(type='nukidora',pai='N')
                self.drawn_by,self.drawn_tile=None,None
            else:
                raise ProtocolError('一番街出现尚未适配的游戏动作。')
            events.append(event)
            if action==11:
                events.extend({'type':'dora','dora_marker':p} for p in self.pending_dora)
                self.pending_dora=[]
        return events

    def settlement(self,data):
        if not self.started: return []
        winners=[p for p in data.get('win_info',[]) if integer(p.get('all_point',0))>0]
        tsumo=integer(data.get('end_type',-1))==1
        if winners and not tsumo: self.pending_reach=None
        events=self.flush_reach()
        deltas=[0]*self.count
        for player in data.get('user_profit',[]):
            deltas[self.actor(player.get('user_id'))]=integer(player.get('point_profit',0))+integer(player.get('extra_profit',0))
        if winners:
            for winner in winners:
                actor=self.actor(winner.get('user_id'))
                if not tsumo and self.last_actor is None: raise ProtocolError('一番街荣和缺少放铳座位。')
                events.append({'type':'hora','actor':actor,'target':actor if tsumo else self.last_actor,
                               'deltas':deltas,'ura_markers':[known_tile(p) for p in winner.get('li_bao_card',[])]})
        else: events.append({'type':'ryukyoku','deltas':deltas})
        events.append({'type':'end_kyoku'})
        self.live=False
        return events
