# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Fetch a pinned Windows four-player engine and its matching source archive."""
import hashlib
import json
from pathlib import Path
import zipfile
import requests

ROOT = Path(__file__).resolve().parent.parent
TAG = 'libriichi_2025.02.26'
BINARY = 'libriichi-3.11-x86_64-pc-windows-msvc.pyd'
BINARY_SHA256 = 'fed91677f6d0d03380b6ef62bb2b19e23be83a556fcef4e05ba206c9e11b65cb'
SOURCE_SHA256 = '965e044cc7c34f2d6dc452a69c379dbc46b8f7896208e34d87b96464d545e2f1'
BINARY_URL = f'https://github.com/shinkuan/Mortal_v4/releases/download/{TAG}/{BINARY}'
SOURCE_URL = f'https://api.github.com/repos/shinkuan/Mortal_v4/zipball/{TAG}'


def verify(directory):
    binary,source = directory/BINARY,directory/(TAG+'-source.zip')
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=BINARY_SHA256:
        raise ValueError('Pinned native engine hash mismatch')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Pinned native engine source archive hash mismatch')
    with zipfile.ZipFile(source) as archive:
        name = next(name for name in archive.namelist() if name.count('/')==1 and name.endswith('/LICENSE'))
        text = archive.read(name).decode('utf-8')
        if 'GNU AFFERO GENERAL PUBLIC LICENSE' not in text or 'Commons Clause' in text:
            raise ValueError('Unexpected upstream engine license')
        if not any(name.endswith('/libriichi/Cargo.toml') for name in archive.namelist()):
            raise ValueError('Missing native engine source')
    return {'repository':'https://github.com/shinkuan/Mortal_v4','tag':TAG,
            'binary':BINARY,'binary_url':BINARY_URL,'binary_sha256':BINARY_SHA256,
            'source':source.name,'source_url':SOURCE_URL,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'license':'AGPL-3.0','python':'3.11','platform':'Windows x64'}


def main():
    directory = ROOT/'build'/'native-engine'
    directory.mkdir(parents=True,exist_ok=True)
    for name,url in ((BINARY,BINARY_URL),(TAG+'-source.zip',SOURCE_URL)):
        path = directory/name
        if not path.exists():
            response = requests.get(url,timeout=90)
            response.raise_for_status()
            pending = path.with_suffix(path.suffix+'.pending')
            pending.write_bytes(response.content)
            pending.replace(path)
    info = verify(directory)
    (directory/'provenance.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2))


if __name__=='__main__':
    main()
