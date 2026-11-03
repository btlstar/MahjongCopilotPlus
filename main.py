# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
""" Mahjong Copilot

Copyright (C) 2024 Latorc (Github page: https://github.com/latorc)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
from gui.main_window import MainWindow
from gui.theme import create_application
from common import utils
from common.log_helper import LogHelper
from common.settings import Settings
from bot_manager import BotManager


def main():
    """ Main entry point """
    LogHelper.config_logging(console=sys.stderr is not None)
    setting = Settings()
    app = create_application()
    app.setQuitOnLastWindowClosed(False)
    # utils.set_dpi_awareness()
    utils.prevent_sleep()
    bot_manager = BotManager(setting)
    gui = MainWindow(setting, bot_manager)
    gui.mainloop()

if __name__ == "__main__":
    main()
