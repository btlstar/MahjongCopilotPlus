# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Akagi v3 MJAI API, based on its published wire protocol (no Rust copied)."""
from copy import deepcopy
from concurrent.futures import Future, TimeoutError as FutureTimeout
from datetime import datetime
import re
import threading
import time
import math
from urllib.parse import urljoin,urlsplit
import requests

from bot.bot import Bot, GameMode
from common.log_helper import LOGGER
from .http_client import direct_session

DEFAULT_URL = 'https://mjapi.shinkuan.me'


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
        self.session = direct_session()
        self._react_lock = threading.Lock()
        self._pending_react = None

    def _request(self,method,route,body=None):
        url = self.url+route
        for hop in range(4):
            try:
                response = self.session.request(method,url,
                    headers={'Authorization':'Bearer '+self.key},json=body,
                    timeout=self.timeout if route=='/v3/react' else 8,allow_redirects=False)
            except requests.exceptions.SSLError:
                raise ValueError('Akagi v3 TLS 证书校验失败，请检查 HTTPS、代理与证书配置。') from None
            except requests.exceptions.ProxyError:
                raise ValueError('Akagi v3 代理连接失败，请检查当前代理与网络设置。') from None
            except requests.exceptions.Timeout:
                raise ValueError('Akagi v3 连接或读取超时，请检查网络线路。') from None
            except requests.exceptions.RequestException:
                raise ValueError('Akagi v3 网络请求失败，请检查服务地址、DNS 和代理连接。') from None
            status = response.status_code
            if status not in (301,302,303,307,308):
                break
            location = response.headers.get('Location')
            if not location:
                raise ValueError(f'Akagi v3 返回 HTTP {status}，但没有提供重定向地址。')
            if hop==3:
                raise ValueError('Akagi v3 重定向次数过多，请检查服务地址。')
            target = urljoin(url,location)
            try:
                current,destination = urlsplit(url),urlsplit(target)
                origin = lambda value:(value.scheme.lower(),value.hostname,(value.port or (443 if value.scheme=='https' else 80)))
                same_origin = origin(current)==origin(destination)
                valid = not destination.username and not destination.password and not destination.fragment
            except ValueError:
                valid,same_origin = False,False
            if not valid or not same_origin:
                try:
                    address = urlsplit(target)
                    host = f'{address.scheme}://{address.hostname or "?"}'
                    if address.port:
                        host += ':'+str(address.port)
                    host = host.replace(self.key,'[已隐藏]') if self.key else host
                except ValueError:
                    host = '无效地址'
                raise ValueError(f'Akagi v3 返回 HTTP {status}，要求跳转到不同域名、端口或协议（{host}）；未转发密钥。请核对服务根地址或代理跳转。')
            if method not in ('GET','HEAD') and status not in (307,308):
                raise ValueError(f'Akagi v3 返回 HTTP {status}，无法确认 POST 语义；未改成 GET 或更换模型。')
            # 307/308 keep the method, JSON body and authorization on this origin.
            url = target
        if response.status_code>=400:
            if 'text/html' in response.headers.get('Content-Type','').lower():
                raise ValueError(f'Akagi v3 返回网页或网络防护错误（HTTP {response.status_code}），请核对服务地址和网络。')
            if response.status_code in (401,403):
                raise ValueError('Akagi v3 密钥未通过授权，或无权使用所选模型；旧版 OT 密钥不保证通用。')
            if response.status_code==404:
                raise ValueError('Akagi v3 接口不存在（HTTP 404），请确认接口选择为 v3，并填写服务根地址。')
            if response.status_code==429:
                raise ValueError('Akagi v3 请求受到限流（HTTP 429），请稍后重试并检查密钥额度。')
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
        if not model:
            raise ValueError('请先为当前玩法选择模型；未使用服务端默认模型。')
        body = {'model':model,'player_id':seat,'events':deepcopy(events)}
        # Requests' socket timeout does not bound DNS, all address attempts,
        # redirects and a slowly streamed body together. Bound the caller's
        # entire wait without touching bot state from the network worker.
        with self._react_lock:
            if self._pending_react is not None and not self._pending_react.done():
                raise ValueError('Akagi v3 上次网络请求仍未结束，本次未发送；未切换模型。')
            pending = Future()
            self._pending_react = pending
            def run():
                try:
                    pending.set_result(self._request('POST','/v3/react',body))
                except Exception as error:
                    pending.set_exception(error)
            threading.Thread(target=run,name='AkagiRequest',daemon=True).start()
        try:
            return pending.result(timeout=self.timeout)
        except FutureTimeout:
            # The worker may still be resolving DNS. Its response is never
            # reused for another decision; at most one request can be in flight.
            raise ValueError(f'Akagi v3 推理总等待超过 {self.timeout:g} 秒，已放弃本次建议；迟到响应不会用于后续出牌。') from None


class BotAkagiV3(Bot):
    """Send seat-censored round history; never silently choose another model."""
    protocol = 'v3'
    def __init__(self,url,key,model_4p='',model_3p=''):
        super().__init__('Akagi v3 API Bot')
        self.client = AkagiV3Client(url,key)
        self.models = {'4p':model_4p.strip(),'3p':model_3p.strip()}
        if not any(self.models.values()):
            raise ValueError('请先获取模型列表并至少选择一个玩法的模型。')
        catalog = self.client.catalog()
        validate_models(catalog,self.models['4p'],self.models['3p'])
        self._supported_modes = [mode for mode,game in ((GameMode.MJ4P,'4p'),(GameMode.MJ3P,'3p'))
                                 if self.models[game] and any(model_game(model)==game for model in catalog)]
        if not self._supported_modes:
            raise ValueError('此密钥没有可用的三麻或四麻模型。')
        self.events = []
        self.mode = None
        self.last_requested_model = None
        self.last_served_model = None
        self.model_confirmed = False
        self.last_error = None
        self.model_checks = ()
        self.last_model_check = None
        self.verified_total = 0
        self.failed_total = 0

    @property
    def supported_modes(self):
        return self._supported_modes

    @property
    def info_str(self):
        if self.model_confirmed:
            return f'Akagi v3 · 服务端回报：{self.last_served_model}'
        return f"Akagi v3 · 配置 4P: {self.models['4p'] or '未配置'} / 3P: {self.models['3p'] or '未配置'} · 尚无推理确认"

    def _init_bot_impl(self,mode=GameMode.MJ4P):
        self.mode = mode
        self.events = []
        self.last_requested_model = self.last_served_model = None
        self.model_confirmed = False
        self.last_error = None
        self.last_model_check = None

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
                    (kind in ('dahai','kakan','ankan','nukidora') and actor!=self.seat) or
                    (input_msg.get('can_act') is True and kind=='dora'))
        if not decision or not any(item['type']=='start_kyoku' for item in self.events):
            return None
        try:
            reaction = self._infer(self.events)
            if reaction and reaction['type']=='reach':
                # Predict the follow-up without permanently appending reach.
                following = self._infer(self.events+[{'type':'reach','actor':self.seat}],phase='reach_discard')
                if not following or following.get('type')!='dahai':
                    raise ValueError('Akagi v3 未返回立直后的出牌，未采用此建议。')
                reaction['reach_dahai'] = following
            self.last_error = None
            return reaction
        except Exception as error:
            self.model_confirmed = False
            self.last_error = str(error)
            raise

    def _safe_model_id(self,value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',value):
            return None
        if self.client.key and self.client.key in value:
            return None
        return value

    def _record_model_check(self,requested,served,status,started,phase):
        self.verified_total += status=='confirmed'
        self.failed_total += status!='confirmed'
        record={'sequence':self.verified_total+self.failed_total,
                'time':datetime.now().astimezone().isoformat(timespec='seconds'),
                'requested':self._safe_model_id(requested),
                'served':self._safe_model_id(served),'status':status,'phase':phase,
                'elapsed_ms':round((time.monotonic()-started)*1000),
                'verified_total':self.verified_total,'failed_total':self.failed_total}
        # Publish whole snapshots, so the GUI never walks a mutating deque.
        self.model_checks = (*self.model_checks[-29:],record)
        self.last_model_check = record
        LOGGER.info('AI_MODEL_CHECK sequence=%s requested=%s served=%s status=%s phase=%s elapsed_ms=%s',
                    record['sequence'],record['requested'],record['served'],status,phase,record['elapsed_ms'])

    def _infer(self,events,phase='decision'):
        game = '3p' if self.mode==GameMode.MJ3P else '4p'
        requested = self.models[game]
        self.last_requested_model = requested or None
        self.last_served_model = None
        self.model_confirmed = False
        served,status,started = None,'request_failed',time.monotonic()
        try:
            payload = self.client.react(requested,self.seat,deepcopy(events))
            served = payload.get('model')
            status = 'missing_model'
            if served is None:
                raise ValueError('Akagi v3 未回报本次推理的模型 ID，无法核验所选模型；未采用建议。')
            status = 'invalid_model'
            if not self._safe_model_id(served):
                raise ValueError('Akagi v3 返回的模型 ID 无效；未采用建议。')
            status = 'mismatch'
            if served!=requested:
                raise ValueError(f'服务端返回模型 {served}，与所选 {requested} 不符；未采用建议。')
            status = 'invalid_reaction'
            reaction = payload.get('reaction')
            if reaction is None:
                self.last_served_model = served
                self.model_confirmed = bool(served)
                status = 'confirmed'
                return None
            # The live v3 service emits `kita` for sanma north extraction,
            # while Copilot's MJAI events and UI use `nukidora`.
            if isinstance(reaction,dict) and reaction.get('type')=='kita':
                reaction = dict(reaction,type='nukidora')
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
            status = 'confirmed'
            return reaction
        finally:
            self._record_model_check(requested,served,status,started,phase)
