# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Loaded model summaries for the footer and detailed diagnostic reports."""
from pathlib import Path


def loaded_models_text(bot):
    models = getattr(bot,'models',None)
    if getattr(bot,'protocol',None)=='v3' and isinstance(models,dict):
        return 'Akagi v3 · 四麻 '+(models.get('4p') or '未配置')+'；三麻 '+(models.get('3p') or '未配置')
    if getattr(bot,'protocol',None)=='legacy':
        return '旧版 OT · 服务端默认'
    if getattr(bot,'model_name',None):
        return 'MJAI · '+bot.model_name
    files = getattr(bot,'model_files',None)
    if isinstance(files,dict):
        return '本地模型 · '+' / '.join(Path(value).name for value in files.values() if value)
    return getattr(bot,'name','AI')


def inference_report_text(bot):
    if getattr(bot,'protocol',None) not in ('v3','legacy'):
        return ''
    if getattr(bot,'model_confirmed',False) and getattr(bot,'last_served_model',None):
        return '最近一次推理回报：'+bot.last_served_model
    return '最近一次推理回报：尚无模型 ID，不能据此确认服务端实际模型。'


def runtime_models_text(manager):
    if manager.is_loading_bot:
        return '当前 AI 正在加载；尚无新的加载结果。'
    bot = manager.bot
    if bot is None:
        return '当前尚无已加载的 AI。'
    text = '当前已加载：'+loaded_models_text(bot)
    if manager.bot_need_update:
        text += '（新配置待切换）'
    return '\n'.join(part for part in (text,inference_report_text(bot)) if part)
