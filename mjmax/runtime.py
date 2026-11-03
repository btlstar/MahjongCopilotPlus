# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Copilot integration for MajsoulMax v2026.07.07."""
from copy import deepcopy

from mitmproxy import http, ctx
from ruamel.yaml import YAML

from common.log_helper import LOGGER
from mjmax.paths import CONFIG
from mjmax.plugin import data_update

VERSION = '2026.07.07-copilot'
DEFAULT_CONFIG = {
    'plugin_enable': {'mod': False},
    'liqi': {'auto_update': False, 'liqi_version': '', 'github_token': ''},
}


def load_settings():
    settings = deepcopy(DEFAULT_CONFIG)
    path = CONFIG / 'settings.yaml'
    if not path.exists():
        path = CONFIG / 'settings.example.yaml'
    if path.exists():
        local = YAML(typ='safe').load(path.read_text(encoding='utf-8')) or {}
        for section in settings:
            settings[section].update(local.get(section, {}))
    return settings


class ModAddon:
    def __init__(self):
        self.settings = load_settings()
        self.parsers = {}
        self.mod_plugin = None
        if self.settings['liqi']['auto_update']:
            try:
                data_update.update(
                    self.settings['liqi']['liqi_version'],
                    self.settings['liqi']['github_token'],
                )
            except Exception:
                LOGGER.warning('皮肤/协议自动更新失败，继续使用已校验的本地资源', exc_info=True)
        # Refresh types before handling traffic; modules imported earlier keep
        # the same pb module object and obtain classes from the refreshed pool.
        from mjmax.proto import liqi_pb2
        liqi_pb2.reload_protocol()
        if not self.settings['plugin_enable']['mod']:
            return
        from mjmax.plugin.mod import mod
        self.mod_plugin = mod(VERSION)
        LOGGER.info('已载入 MajsoulMax %s：%d 个角色 / %d 套皮肤',
                    VERSION, len(self.mod_plugin.max_data['character']), len(self.mod_plugin.max_data['skin']))

    def websocket_start(self, flow: http.HTTPFlow):
        if self.mod_plugin is not None and flow.request.path != '/ob':
            import liqi
            self.parsers[flow.id] = liqi.LiqiProto()

    def websocket_end(self, flow: http.HTTPFlow):
        self.parsers.pop(flow.id, None)

    def websocket_message(self, flow: http.HTTPFlow):
        if self.mod_plugin is None or flow.request.path == '/ob' or flow.websocket is None:
            return
        message = flow.websocket.messages[-1]
        if message.injected or not isinstance(message.content, bytes) or not message.content:
            return
        if message.content[0] not in (1, 2, 3):
            return
        if flow.id not in self.parsers:
            self.websocket_start(flow)
        parser = self.parsers[flow.id]
        original = message.content
        try:
            modify, drop, content, inject, injected_content = self.mod_plugin.main(message, parser)
            if modify:
                message.content = content
            if drop:
                message.drop()
            # Track the method actually sent to the server (including rewritten
            # loginBeat requests), in this WebSocket's request-id space only.
            if not drop:
                parser.parse(message)
            if inject:
                ctx.master.commands.call('inject.websocket', flow, True, injected_content, False)
        except Exception:
            # A new or unsupported cosmetic message must not break the proxy.
            message.content = original
            LOGGER.debug('皮肤模块未处理消息，保留原始内容 (flow=%s)', flow.id, exc_info=True)
