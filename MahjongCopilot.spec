# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
import os
import playwright
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)
driver = Path(playwright.__file__).parent / 'driver'
native_3p = root / 'libriichi3p' / f'libriichi3p-{sys.version_info.major}.{sys.version_info.minor}-x86_64-pc-windows-msvc.pyd'

a = Analysis(
    ['desktop_entry.py'],
    pathex=[],
    binaries=[(str(native_3p), 'libriichi3p')] if os.environ.get('PLUS_INCLUDE_3P')=='1' else [],
    datas=[('mjmax/config/max_data.yaml', 'mjmax/config'),
           ('mjmax/config/data_version.json', 'mjmax/config'),
           ('mjmax/config/settings.example.yaml', 'mjmax/config'),
           ('mjmax/proto/liqi.desc', 'mjmax/proto'),
           ('mjmax/proto/liqi.json', 'mjmax/proto'),
           ('resources', 'resources'),
           (str(driver), 'playwright/driver')]
          + collect_data_files('mitmproxy'),
    hiddenimports=collect_submodules('mitmproxy.proxy.layers')
                  + ['mjmax.proto.basic_pb2', 'mjmax.proto.liqi_pb2', 'libriichi3p'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'scipy', 'IPython', 'pytest', 'notebook', 'tensorboard',
              'PyQt5', 'PyQt6', 'PySide2'],
    noarchive=False,
)
# Qt uses Windows' unsuffixed ICU API. A Git/MinGW ICU from PATH exports
# version-suffixed symbols and must not shadow the operating-system DLL.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll','icudt78.dll'}]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MahjongCopilotPlus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\icon.ico'],
    version='resources/version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MahjongCopilotPlus',
)
