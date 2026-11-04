# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Read explicit inference model IDs; never infer a model from tensor shapes."""
import re


def inference_model_report(payload,headers,secret=''):
    reports = []
    def add(value,source):
        if (isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}',value)
                and (not secret or secret not in value)):
            reports.append((value,source))
    if isinstance(payload,dict):
        for field in ('model','model_id','model_name'):
            add(payload.get(field),'JSON '+field)
    for key,value in headers.items():
        if key.lower() in ('x-model','x-model-id','x-model-name'):
            add(value,key)
    values = {value for value,_ in reports}
    if len(values)>1:
        return None,'本次推理的模型回报不一致，尚未确认。'
    if reports:
        return reports[0][0],'推理响应：'+', '.join(source for _,source in reports)
    return None,'本次旧版 OT 推理响应未提供明确的模型 ID，无法确认具体模型。'
