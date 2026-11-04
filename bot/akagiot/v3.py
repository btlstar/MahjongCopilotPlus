# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Akagi v3 MJAI API, based on its published wire protocol (no Rust copied)."""
from copy import deepcopy
import math
import requests

from bot.bot import Bot, GameMode

DEFAULT_URL = 'https://mjapi.shinkuan.me'
DEFAULT_4P = '4p-akg-v8b-preview'
DEFAULT_3P = '3p-akg-v9'


def model_game(model):
    game = str(model.get('game','')).lower()
    if game in ('4p','3p'):
        return game
    return str(model.get('id',''))[:2].lower()


def validate_models(catalog,model_4p,model_3p):
    by_id = {model['id']:model for model in catalog}
    for game,selected in (('4p',model_4p),('3p',model_3p)):
        if selected and (selected not in by_id or model_game(by_id[selected])!=game):
            raise ValueError(f'{selected} 不在此密钥的 {game} 可用模型列表中；未改用其他模型。')


class AkagiV3Client:
    def __init__(self,url,key,timeout=3):
        self.url = url.strip().rstrip('/')
        if self.url.endswith('/v3'):
            self.url = self.url[:-3]
        self.key = key.strip()
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self,method,route,body=None):
        response = self.session.request(method,self.url+route,
            headers={'Authorization':'Bearer '+self.key},json=body,
            timeout=self.timeout if route=='/v3/react' else 8,allow_redirects=False)
        if response.status_code>=400 or response.status_code in (301,302,303,307,308):
            if 'text/html' in response.headers.get('Content-Type','').lower():
                raise ValueError(f'Akagi v3 返回网页或网络防护错误（HTTP {response.status_code}），请核对服务地址和网络。')
            if response.status_code in (401,403):
                raise ValueError('Akagi v3 密钥未通过授权，或无权使用所选模型；旧版 OT 密钥不保证通用。')
            raise ValueError(f'Akagi v3 请求失败（HTTP {response.status_code}），未切换到默认模型。')
        try:
            result = response.json()
        except ValueError:
            raise ValueError('Akagi v3 未返回有效 JSON，请核对服务根地址。') from None
        if not isinstance(result,dict):
            raise ValueError('Akagi v3 返回格式不正确。')
        return result

    def catalog(self):
        self._request('GET','/v3/key')
        payload = self._request('GET','/v3/models')
        models = payload.get('models')
        if not isinstance(models,list) or not all(isinstance(m,dict) and isinstance(m.get('id'),str) for m in models):
            raise ValueError('Akagi v3 没有返回有效的模型列表。')
        return models

    def react(self,model,seat,events):
        body = {'player_id':seat,'events':events}
        if model:
            body['model'] = model
        return self._request('POST','/v3/react',body)


class BotAkagiV3(Bot):
    """Send seat-censored round history; never silently choose another model."""
    def __init__(self,url,key,model_4p=DEFAULT_4P,model_3p=DEFAULT_3P):
        super().__init__('Akagi v3 API Bot')
        self.client = AkagiV3Client(url,key)
        self.models = {'4p':model_4p.strip(),'3p':model_3p.strip()}
        catalog = self.client.catalog()
        validate_models(catalog,self.models['4p'],self.models['3p'])
        self._supported_modes = [mode for mode,game in ((GameMode.MJ4P,'4p'),(GameMode.MJ3P,'3p'))
                                 if any(model_game(model)==game for model in catalog)]
        if not self._supported_modes:
            raise ValueError('此密钥没有可用的三麻或四麻模型。')
        self.events = []
        self.mode = None
        self.last_requested_model = None
        self.last_served_model = None
        self.model_confirmed = False
        self.last_error = None

    @property
    def supported_modes(self):
        return self._supported_modes

    @property
    def info_str(self):
        if self.model_confirmed:
            return f'Akagi v3 · 服务端回报：{self.last_served_model}'
        return f"Akagi v3 · 请求 4P: {self.models['4p'] or '服务端默认'} / 3P: {self.models['3p'] or '服务端默认'} · 尚无推理确认"

    def _init_bot_impl(self,mode=GameMode.MJ4P):
        self.mode = mode
        self.events = []
        self.last_requested_model = self.last_served_model = None
        self.model_confirmed = False
        self.last_error = None

    def _event(self,message):
        event = deepcopy(message)
        event.pop('can_act',None)
        kind = event['type']
        if kind=='start_game':
            return {'type':kind,'names':['']*4}
        if kind=='start_kyoku':
            event['scores'] = (list(event['scores'])+[0]*4)[:4]
            hands = event['tehais']
            event['tehais'] = [list(hands[i]) if i==self.seat and i<len(hands) else ['?']*13 for i in range(4)]
        elif kind=='tsumo' and event.get('actor')!=self.seat:
            event['pai'] = '?'
        elif kind=='reach':
            return {'type':kind,'actor':event['actor']}
        return event

    def react(self,input_msg):
        event = self._event(input_msg)
        kind,actor = event['type'],event.get('actor')
        if kind=='start_game':
            self.events = [event]
        elif kind=='start_kyoku':
            start = next((item for item in self.events if item['type']=='start_game'),{'type':'start_game','names':['']*4})
            self.events = [start,event]
        else:
            self.events.append(event)
        if not input_msg.get('can_act',True):
            return None
        decision = ((kind in ('tsumo','chi','pon') and actor==self.seat) or
                    (kind in ('dahai','kakan','ankan','nukidora') and actor!=self.seat))
        if not decision or not any(item['type']=='start_kyoku' for item in self.events):
            return None
        try:
            reaction = self._infer(self.events)
            if reaction and reaction['type']=='reach':
                # Predict the follow-up without permanently appending reach.
                following = self._infer(self.events+[{'type':'reach','actor':self.seat}])
                if not following or following.get('type')!='dahai':
                    raise ValueError('Akagi v3 未返回立直后的出牌，未采用此建议。')
                reaction['reach_dahai'] = following
            self.last_error = None
            return reaction
        except Exception as error:
            self.model_confirmed = False
            self.last_error = str(error)
            raise

    def _infer(self,events):
        game = '3p' if self.mode==GameMode.MJ3P else '4p'
        requested = self.models[game]
        self.last_requested_model = requested or None
        self.last_served_model = None
        self.model_confirmed = False
        payload = self.client.react(requested,self.seat,deepcopy(events))
        served = payload.get('model')
        if served is not None and (not isinstance(served,str) or not served.strip()):
            raise ValueError('Akagi v3 返回的模型 ID 无效。')
        if requested and served and served!=requested:
            raise ValueError(f'服务端返回模型 {served}，与所选 {requested} 不符；未采用建议。')
        reaction = payload.get('reaction')
        if reaction is None:
            self.last_served_model = served
            self.model_confirmed = bool(served)
            return None
        allowed = {'none','dahai','reach','chi','pon','daiminkan','ankan','kakan','hora','ryukyoku','nukidora'}
        if not isinstance(reaction,dict) or reaction.get('type') not in allowed:
            raise ValueError('Akagi v3 返回的动作格式不正确。')
        if reaction['type']!='none' and reaction.get('actor')!=self.seat:
            raise ValueError('Akagi v3 返回了其他座位的动作，未采用建议。')
        reaction = deepcopy(reaction)
        reaction.pop('meta',None)
        options = []
        for item in payload.get('candidates') or []:
            if not isinstance(item,dict):
                continue
            action,probability = item.get('action'),item.get('prob')
            if not isinstance(action,str) or not isinstance(probability,(float,int)) or not math.isfinite(probability) or not 0<=probability<=1:
                continue
            action = action.split(':',1)[1] if action.startswith('dahai:') else action
            action = {'chi_low':'chi','chi_mid':'chi','chi_high':'chi','kan':'kan_select','kita':'nukidora'}.get(action,action)
            options.append((action,float(probability)))
        reaction['meta_options'] = options
        self.last_served_model = served
        self.model_confirmed = bool(served)
        return reaction
