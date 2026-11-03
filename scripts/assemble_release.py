# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Collect license materials, audit a clean portable tree, and create release assets."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_NAMES = {'settings.mod.yaml','.env','mitmproxy-ca.pem'}


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def collect_licenses(package):
    destination = package/'LICENSES'/'dependencies'
    destination.mkdir(parents=True,exist_ok=True)
    packages = []
    for dist in sorted(metadata.distributions(),key=lambda item:item.metadata.get('Name','').lower()):
        name = dist.metadata.get('Name','unknown')
        entry = {'name':name,'version':dist.version,
                 'license':dist.metadata.get('License-Expression') or dist.metadata.get('License',''),
                 'project_urls':dist.metadata.get_all('Project-URL',[]),'license_files':[]}
        for relative in dist.files or []:
            lowered = str(relative).lower()
            if not any(word in Path(lowered).name for word in ('license','copying','notice')):
                continue
            path = Path(dist.locate_file(relative))
            if not path.is_file() or path.suffix.lower() in ('.py','.pyc','.pyd','.dll'):
                continue
            target = destination/(name+'-'+dist.version)/str(relative).replace('..','_parent_')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
            entry['license_files'].append(target.relative_to(package).as_posix())
        packages.append(entry)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license,package/'LICENSES'/'Python-LICENSE.txt')
    # Playwright's driver/Chromium notices are included with their binary tree.
    (package/'DEPENDENCIES.json').write_text(json.dumps(packages,ensure_ascii=False,indent=2),encoding='utf-8')


def verify_clean(package):
    settings = json.loads((package/'settings.json').read_text(encoding='utf-8'))
    for key in ('akagi_ot_apikey','mjapi_user','mjapi_secret','akagi_ot_url','model_file','model_file_3p'):
        if settings.get(key):
            raise ValueError('Nonempty private/default field: '+key)
    if settings.get('enable_automation') or settings.get('auto_join_game'):
        raise ValueError('Automatic actions must default to off')
    for path in package.rglob('*'):
        relative = path.relative_to(package)
        if not path.is_file():
            continue
        # Third-party package files named models/logs are not runtime user data.
        if relative.parts[0] in ('browser_data','mitm_config','log','logs','temp','models','backups'):
            raise ValueError('Personal runtime folder: '+str(relative))
        if path.name in PRIVATE_NAMES or path.suffix.lower() in ('.key','.pfx','.p12','.pth','.onnx'):
            raise ValueError('Private key/config/model: '+str(relative))
        if path.suffix.lower()=='.pem' and b'PRIVATE KEY' in path.read_bytes():
            raise ValueError('Private key: '+str(relative))
    if not (package/'MahjongCopilotPlus.exe').is_file() or (package/'MahjongCopilot-UI.exe').exists():
        raise ValueError('Unexpected application entry point')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=ROOT/'dist'/'MahjongCopilotPlus')
    parser.add_argument('--output',type=Path,default=ROOT/'dist'/'release')
    args = parser.parse_args()
    package = args.package.resolve(strict=True)
    version = (ROOT/'version').read_text(encoding='utf-8').strip()
    collect_licenses(package)
    for name in ('docs','assets/screenshots'):
        shutil.copytree(ROOT/name,package/name,dirs_exist_ok=True)
    for name in ('readme.md','DESKTOP.md','CHANGELOG.md','NOTICE.md','THIRD_PARTY_NOTICES.md',
                 'CONTRIBUTING.md','SECURITY.md','version'):
        shutil.copy2(ROOT/name,package/name)
    (package/'START-HERE.txt').write_text(
        'MahjongCopilotPlus '+version+' - Windows x64\n\n'
        'Extract the ENTIRE zip to a writable local folder. Run MahjongCopilotPlus.exe.\n'
        'Keep _internal and other files beside the exe. Python installation is not needed.\n'
        'Configure your AI service or supply compatible local model weights.\n'
        'Models and API accounts are not included. Automatic actions are off by default.\n'
        'The optional 3-player extension and external-client proxy injector are not included.\n'
        'See docs/INSTALL.md, THIRD_PARTY_NOTICES.md and SOURCE_PROVENANCE.md.\n',encoding='utf-8')
    info = {'product':'MahjongCopilotPlus','version':version,'platform':'Windows x64',
            'python':platform.python_version(),'built_at_utc':datetime.now(timezone.utc).isoformat(),
            'models_included':False,'credentials_included':False,
            'three_player_extension_included':False,'proxinject_binaries_included':False,
            'engine':json.loads((package/'ENGINE_PROVENANCE.json').read_text(encoding='utf-8'))}
    (package/'BUILD_INFO.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    shutil.copy2(ROOT/'docs'/'SOURCE_PROVENANCE.md',package/'SOURCE_PROVENANCE.md')
    verify_clean(package)
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    archive = output/f'MahjongCopilotPlus-{version}-windows-x64.zip'
    if archive.exists():
        raise FileExistsError('Preserve existing release asset: '+str(archive))
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                bundle.write(path,'MahjongCopilotPlus/'+path.relative_to(package).as_posix())
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha256(archive)},indent=2))


if __name__=='__main__':
    main()
