# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Paths shared by the source and frozen application."""
from pathlib import Path
import sys


ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
MJMAX = ROOT / 'mjmax'
if getattr(sys, 'frozen', False) and not MJMAX.exists():
    MJMAX = Path(sys._MEIPASS) / 'mjmax'
CONFIG = MJMAX / 'config'
PROTO = MJMAX / 'proto'
