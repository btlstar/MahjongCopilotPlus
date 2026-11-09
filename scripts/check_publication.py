# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Check prospective repository files without uploading, staging or printing secrets."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIRS = {'venv','.venv','browser_data','mitm_config','log','logs','temp','models','backups','_internal','build','dist','__pycache__'}
BINARY_EXTENSIONS = {'.exe','.dll','.pyd','.so','.dylib','.pth','.pt','.onnx','.pem','.key','.pfx','.p12'}
TEXT_EXTENSIONS = {'.py','.md','.json','.yaml','.yml','.bat','.spec','.txt','.svg'}


def files():
    if (ROOT/'.git').is_dir():
        output = subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=ROOT)
        return sorted({ROOT/name.decode('utf-8') for name in output.split(b'\0') if name and (ROOT/name.decode('utf-8')).is_file()})
    return sorted(path for path in ROOT.rglob('*') if path.is_file() and not PRIVATE_DIRS.intersection(path.relative_to(ROOT).parts))


def main():
    errors = []
    candidates = files()
    for path in candidates:
        relative = path.relative_to(ROOT)
        name = relative.as_posix()
        if PRIVATE_DIRS.intersection(relative.parts) or path.suffix.lower() in BINARY_EXTENSIONS:
            errors.append(f'非源码／私人文件进入发布候选：{name}')
        if path.name in ('AGENTS.md','COMMIT_MESSAGE.txt','COMMIT_MESSAGE.md','VALIDATION.md'):
            errors.append(f'内部工作材料进入发布候选：{name}')
        if path.name in ('settings.json','settings.yaml','settings.mod.yaml'):
            errors.append(f'私人配置进入发布候选：{name}')
        if path.stat().st_size>=95*1024*1024:
            errors.append(f'文件接近 GitHub 单文件大小限制：{name}')
        if path.suffix not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding='utf-8-sig')
        if re.search(r'(?i)[A-Z]:[\\/]+Users[\\/]+Administrator[\\/]',text):
            errors.append(f'含本机个人绝对路径：{name}')
        if re.search(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',text):
            errors.append(f'疑似有效凭据／私钥，请人工检查：{name}')
        if path.suffix=='.py':
            try:
                ast.parse(text,filename=name)
            except SyntaxError as error:
                errors.append(f'Python 语法错误：{name}:{error.lineno}')
        if path.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',text):
                target = target.strip('<>').split('#',1)[0]
                if not target or re.match(r'[a-z]+:',target) or target.startswith('//'):
                    continue
                if not (path.parent/unquote(target)).exists():
                    errors.append(f'文档本地链接不存在：{name} -> {target}')
    for name in ('LICENSE','NOTICE.md','THIRD_PARTY_NOTICES.md','LICENSES/AGPL-3.0.txt','readme.md','settings.example.json'):
        if not (ROOT/name).is_file():
            errors.append(f'缺少发布文件：{name}')
    if 'GNU GENERAL PUBLIC LICENSE' not in (ROOT/'LICENSE').read_text(encoding='utf-8')[:200]:
        errors.append('GPL 许可证原文不完整')
    example = json.loads((ROOT/'settings.example.json').read_text(encoding='utf-8'))
    for key in ('akagi_ot_apikey','akagi_v3_apikey','mjapi_secret','mjapi_user'):
        if example.get(key):
            errors.append(f'示例配置不应包含 {key} 的真实值')
    for key in ('riichicity_client_path','riichicity_unlock_path','riichicity_unlock_ca','riichicity_injector_path','riichicity_upstream_proxy'):
        if example.get(key):
            errors.append(f'公开模板不应包含本机一番街配置：{key}')
    if example.get('riichicity_unlock_enabled') or example.get('riichicity_capture_method','manual')!='manual':
        errors.append('公开模板不应默认启动外部解锁或进程注入工具')
    if example.get('enable_automation') or example.get('auto_join_game'):
        errors.append('公开模板应默认关闭自动操作')
    manifest = json.loads((ROOT/'mjmax/config/data_version.json').read_text(encoding='utf-8'))
    for name,path in (('max_data.yaml',ROOT/'mjmax/config/max_data.yaml'),('liqi.desc',ROOT/'mjmax/proto/liqi.desc')):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256'][name]:
            errors.append(f'资源摘要与版本记录不符：{name}')
    print(json.dumps({'ok':not errors,'candidate_files':len(candidates),'errors':errors},ensure_ascii=False,indent=2))
    return 1 if errors else 0


if __name__=='__main__':
    sys.exit(main())
