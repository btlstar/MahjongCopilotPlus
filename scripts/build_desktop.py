# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Build a portable Plus directory from public inputs, never from user settings."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = 'MahjongCopilotPlus'


def install_verified_engine(package):
    """Use the source-tagged engine, never redistribute the legacy wheel."""
    from fetch_engine import verify
    directory = ROOT/'build'/'native-engine'
    info = verify(directory)
    target = package/'_internal'/'libriichi'
    target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(directory/info['binary'],target/'libriichi.pyd')
    # PyInstaller analyses the pip fallback too; it is not this release's engine.
    legacy = package/'_internal'/'riichi'
    if legacy.is_dir():
        for path in legacy.glob('*.pyd'):
            path.unlink()
    sources = package/'SOURCES'
    sources.mkdir(exist_ok=True)
    shutil.copy2(directory/info['source'],sources/info['source'])
    (package/'ENGINE_PROVENANCE.json').write_text(json.dumps(info,indent=2),encoding='utf-8')


def copy_public_defaults(package):
    """Also used by the release regression test; no live-config paths allowed."""
    (package/'mjmax'/'config').mkdir(parents=True,exist_ok=True)
    for name in ('max_data.yaml','data_version.json','settings.example.yaml'):
        shutil.copy2(ROOT/'mjmax'/'config'/name,package/'mjmax'/'config'/name)
    shutil.copy2(ROOT/'mjmax'/'config'/'settings.example.yaml',package/'mjmax'/'config'/'settings.yaml')
    (package/'mjmax'/'proto').mkdir(parents=True,exist_ok=True)
    for name in ('liqi.desc','liqi.json'):
        shutil.copy2(ROOT/'mjmax'/'proto'/name,package/'mjmax'/'proto'/name)
    shutil.copytree(ROOT/'resources',package/'resources',dirs_exist_ok=True)
    shutil.copy2(ROOT/'settings.example.json',package/'settings.json')
    for name in ('version','LICENSE','NOTICE.md','THIRD_PARTY_NOTICES.md','readme.md'):
        shutil.copy2(ROOT/name,package/name)
    shutil.copytree(ROOT/'LICENSES',package/'LICENSES',dirs_exist_ok=True)
    (package/'proxinject').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'proxinject'/'LICENSE',package/'proxinject'/'LICENSE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-3p',action='store_true',help='Include a locally supplied, licensed Python-matched three-player extension')
    parser.add_argument('--include-proxinject',action='store_true',help='Include locally supplied proxinject binaries after checking their redistribution terms')
    args = parser.parse_args()
    os.chdir(ROOT)
    if sys.version_info[:2]!=(3,11):
        parser.error('当前固定的发布引擎需要 Python 3.11 x64')
    from fetch_engine import verify
    try:
        verify(ROOT/'build'/'native-engine')
    except (OSError,ValueError,StopIteration):
        parser.error('请先运行 python scripts/fetch_engine.py，准备经校验的原生库及对应源码')
    native = ROOT/'libriichi3p'/f'libriichi3p-{sys.version_info.major}.{sys.version_info.minor}-x86_64-pc-windows-msvc.pyd'
    if args.include_3p and not native.is_file():
        parser.error(f'缺少匹配的原生库：{native.name}；见 docs/INSTALL.md')
    if args.include_proxinject and not (ROOT/'proxinject'/'proxinjector-cli.exe').is_file():
        parser.error('请先按安装说明准备 proxinject，并核对其分发许可')
    import playwright
    browsers = Path(playwright.__file__).parent/'driver'/'package'/'.local-browsers'
    if not browsers.is_dir() or not any(browsers.iterdir()):
        parser.error("请先设置 PLAYWRIGHT_BROWSERS_PATH=0 并执行 python -m playwright install chromium")
    (ROOT/'build').mkdir(exist_ok=True)
    # Build into a fresh location so a previous private build cannot leave files.
    import tempfile
    output_root = Path(tempfile.mkdtemp(prefix='plus-build-',dir=ROOT/'build'))
    env = os.environ.copy()
    env['PLAYWRIGHT_BROWSERS_PATH'] = '0'
    env['PLUS_INCLUDE_3P'] = '1' if args.include_3p else '0'
    with (ROOT/'build'/'exe-build.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(output_root),
                       str(ROOT/'MahjongCopilot.spec')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    package = output_root/APP_NAME
    copy_public_defaults(package)
    install_verified_engine(package)
    if args.include_3p:
        (package/'libriichi3p').mkdir(exist_ok=True)
        shutil.copy2(native,package/'libriichi3p'/native.name)
    if args.include_proxinject:
        for path in (ROOT/'proxinject').iterdir():
            if path.suffix.lower() in ('.exe','.dll'):
                shutil.copy2(path,package/'proxinject'/path.name)
    (ROOT/'dist').mkdir(exist_ok=True)
    destination = ROOT/'dist'/APP_NAME
    if destination.exists():
        parser.error(f'新构建已保存在 {package}。请先手动归档旧的 dist/{APP_NAME}，避免覆盖其配置')
    shutil.move(str(package),str(destination))
    print(json.dumps({'portable':str(destination),'exe':APP_NAME+'.exe',
                      'include_3p':args.include_3p,'include_proxinject':args.include_proxinject,
                      'note':'发布前仍需执行 docs/PUBLISHING.md 中的二进制与许可验收'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
