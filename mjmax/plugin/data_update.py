# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Download and validate the matching protocol/skin data from MajsoulData."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests
from ruamel.yaml import YAML

from common.log_helper import LOGGER
from mjmax.paths import CONFIG, PROTO
from mjmax.proto.protocol import build_protocol

RELEASE_URL = 'https://api.github.com/repos/Avenshy/MajsoulData/releases/latest'
FILES = {'max_data.yaml': CONFIG / 'max_data.yaml', 'liqi.desc': PROTO / 'liqi.desc'}
MANIFEST = CONFIG / 'data_version.json'


def validate_max_data(blob):
    data = YAML(typ='safe').load(blob.decode('utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('max_data.yaml 不是资源表')
    for key in ('character', 'skin', 'title', 'item', 'loading_image', 'endings'):
        values = data.get(key)
        if not isinstance(values, list) or not values or any(type(v) is not int or v <= 0 for v in values):
            raise ValueError(f'max_data.yaml 的 {key} 数据无效')
    if not isinstance(data.get('emoji'), dict):
        raise ValueError('max_data.yaml 缺少 emoji 数据')
    for char, emojis in data['emoji'].items():
        if type(char) is not int or not isinstance(emojis, list) or any(type(v) is not int for v in emojis):
            raise ValueError('max_data.yaml 的 emoji 数据无效')
    return data


def _sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def _install(blobs):
    """Stage every file before replacing anything; roll back on a write failure."""
    previous = {path: path.read_bytes() if path.exists() else None for path in blobs}
    staged = {}
    replaced = []
    try:
        for path, blob in blobs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
                staged[path] = Path(f.name)
                f.write(blob)
        for path, tmp in staged.items():
            os.replace(tmp, path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous[path])
        raise
    finally:
        for tmp in staged.values():
            tmp.unlink(missing_ok=True)


def update(version='', token='', force=False):
    headers = {'X-GitHub-Api-Version': '2022-11-28', 'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    response = requests.get(RELEASE_URL, headers=headers, timeout=20)
    response.raise_for_status()
    release = response.json()
    new_version = release['tag_name']
    if MANIFEST.exists() and not force:
        local = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if local.get('version') == new_version and all(
            path.exists() and _sha256(path.read_bytes()) == local.get('sha256', {}).get(name)
            for name, path in FILES.items()
        ):
            LOGGER.info('皮肤资源及协议无需更新，当前版本：%s', new_version)
            return new_version
    assets = {item['name']: item for item in release.get('assets', [])}
    if not FILES.keys() <= assets.keys():
        raise FileNotFoundError('MajsoulData 发布页缺少配套的 max_data.yaml / liqi.desc')
    downloads = {}
    for name in FILES:
        LOGGER.info('正在下载 %s', name)
        response = requests.get(assets[name]['browser_download_url'], timeout=30)
        response.raise_for_status()
        downloads[name] = response.content
        expected = assets[name].get('digest')
        if expected and expected.startswith('sha256:') and expected[7:] != _sha256(response.content):
            raise ValueError(f'{name} 的 SHA256 校验失败')
    data = validate_max_data(downloads['max_data.yaml'])
    _, _, methods = build_protocol(downloads['liqi.desc'])
    manifest = {
        'version': new_version,
        'source': release['html_url'],
        'majsoulmax_version': 'v2026.07.07',
        'sha256': {name: _sha256(blob) for name, blob in downloads.items()},
        'counts': {key: len(values) for key, values in data.items()},
    }
    blobs = {FILES[name]: blob for name, blob in downloads.items()}
    blobs[PROTO / 'liqi.json'] = json.dumps(methods, separators=(',', ':')).encode('utf-8')
    blobs[MANIFEST] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    _install(blobs)
    LOGGER.info('皮肤资源及协议更新成功：%s (%d 个皮肤)', new_version, len(data['skin']))
    return new_version


if __name__ == '__main__':
    import argparse
    from common.log_helper import LogHelper
    parser = argparse.ArgumentParser(description='更新 CopilotMax 的皮肤资源及雀魂协议')
    parser.add_argument('--force', action='store_true', help='重新下载并校验全部数据')
    args = parser.parse_args()
    LogHelper.config_logging(file=False)
    print(update(force=args.force))
