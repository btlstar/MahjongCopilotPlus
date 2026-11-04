# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Akagi HTTP transport: direct at application level; TUN routing is external."""
import requests


def direct_session():
    session = requests.Session()
    session.trust_env = False
    return session
