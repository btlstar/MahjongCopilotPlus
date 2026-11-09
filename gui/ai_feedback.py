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
    report = inference_report_text(bot)
    check = getattr(bot,'last_model_check',None)
    if check and check['status']!='confirmed':
        report = '最近一次推理：'+CHECK_STATUS.get(check['status'],'未核验')+'；未采用建议。'
    if hasattr(bot,'verified_total'):
        report += f"\n逐次核验：通过 {bot.verified_total} 次，未采用 {bot.failed_total} 次（本次加载）。"
    return '\n'.join(part for part in (text,report) if part)


CHECK_STATUS = {'confirmed':'一致','mismatch':'模型不符','missing_model':'未回报模型',
                'invalid_model':'模型 ID 无效','request_failed':'请求失败','invalid_reaction':'动作无效'}


def inference_footer_text(bot):
    """Use the completed response, not the saved draft, for verification."""
    if getattr(bot,'protocol',None)!='v3':
        return ''
    check = getattr(bot,'last_model_check',None)
    if not check:
        return ''
    game = getattr(getattr(bot,'mode',None),'value','').lower()
    model = getattr(bot,'models',{}).get(game)
    if not model or check.get('requested')!=model:
        return ''
    title = '四麻' if game=='4p' else '三麻'
    status = ('已核验' if check['status']=='confirmed' else CHECK_STATUS.get(check['status'],'未核验'))
    return f'{title} {model} · {status}'


def model_check_history_text(bot):
    checks = getattr(bot,'model_checks',())
    if not checks:
        return ''
    lines = ['最近 '+str(len(checks))+' 次推理核验（本次加载）：']
    for check in checks:
        phase = '立直后出牌' if check['phase']=='reach_discard' else '决策'
        lines.append(f"#{check['sequence']} {check['time']} · {phase} · "
                     f"{check['requested'] or '—'} → {check['served'] or '未回报'} · "
                     f"{CHECK_STATUS.get(check['status'],'失败')} · {check['elapsed_ms']} ms")
    return '\n'.join(lines)
