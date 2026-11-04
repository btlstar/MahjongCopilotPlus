# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
""" Bot for Akagi online-trained API"""
from common.log_helper import LOGGER
from bot.bot import BotMjai, GameMode
from bot.akagiot.engine import MortalEngineAkagiOt
from .http_client import direct_session
    
    
class BotAkagiOt(BotMjai):
    """ Bot implementation for Akagi online-trained API """
    protocol = 'legacy'
    
    def __init__(self, url:str, apikey:str) -> None:
        super().__init__("Akagi OT API Bot")
        self.url = url
        self.apikey = apikey        
        self.active_engine = None
        self._check()
        
    def _check(self):
        # check authorization
        headers = {
            'Authorization': self.apikey,
        }
        with direct_session() as session:
            r = session.post(f"{self.url}/check", headers=headers, timeout=5)
        r.raise_for_status()
        r_json = r.json()
        if r_json["result"] == "success":
            LOGGER.info("Akagi OT API check success")
        else:
            raise ValueError('AkagiOT authorization failed')
        
    @property
    def supported_modes(self) -> list[GameMode]:
        """ return suported game modes"""
        return [GameMode.MJ4P, GameMode.MJ3P]        
   

    def _get_engine(self, mode: GameMode):
        engine = MortalEngineAkagiOt(self.apikey, self.url, mode)
        self.active_engine = engine
        return engine

    @property
    def last_served_model(self):
        return getattr(self.active_engine,'last_served_model',None)

    @property
    def model_confirmed(self):
        return getattr(self.active_engine,'model_confirmed',False)

    @property
    def model_report_note(self):
        return getattr(self.active_engine,'model_report_note','尚无旧版 OT 推理响应；授权检查不代表具体模型。')

    @property
    def info_str(self):
        return super().info_str+' · '+('服务端回报：'+self.last_served_model if self.model_confirmed else self.model_report_note)
