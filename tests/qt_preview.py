# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Disposable offline UI fixture: never opens a game or reads account settings."""
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from gui.theme import create_application
from gui.main_window import MainWindow
from bot_manager import BotManager
from common.settings import Settings
from common.log_helper import LOGGER


def create_preview(settings,*,register_hotkey=False):
    manager = BotManager(settings)
    info = SimpleNamespace(my_tehai=['2m','3m','4m','6m','6m','3p','4p','5pr','3s','4s','5s','S','N'],
                           my_tsumohai='2s',bakaze='E',kyoku=1,honba=0)
    reaction = {'type':'dahai','pai':'6m','meta_options':[('6m',.67),('S',.21),('N',.08)]}
    manager.game_state = SimpleNamespace(get_game_info=lambda:info,get_pending_reaction=lambda:reaction,
                                        is_ms_syncing=False,is_bot_calculating=False)
    manager.bot = SimpleNamespace(name='Akagi OT API Bot')
    manager.active_model_type = 'AkagiOT'
    manager.bot_need_update = False
    return MainWindow(settings,manager,start_backend=False,register_hotkey=register_hotkey)


if __name__=='__main__':
    import tempfile
    app = create_application()
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(str(Path(directory)/'settings.json'))
        window = create_preview(settings)
        window.mainloop()
