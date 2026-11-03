# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Tile/action presentation shared by desktop and in-game advice."""
import re
from .mj_helper import MJAI_TILE_2_UNICODE, ActionUnicode

NUMBERS = '一二三四五六七八九'
HONORS = {'E':'東', 'S':'南', 'W':'西', 'N':'北', 'P':'白', 'F':'發', 'C':'中', '?':'?'}
TILE_COLORS = {'m':'#ab494b', 'p':'#406388', 's':'#347558', 'z':'#292a2d'}


def tile_data(code):
    if re.fullmatch(r'[1-9][mps]r?', code):
        suit = code[1]
        return {'code': code, 'value': NUMBERS[int(code[0])-1],
                'suit': {'m':'萬','p':'筒','s':'索'}[suit],
                'color': TILE_COLORS[suit], 'red': code.endswith('r')}
    return {'code': code, 'value': HONORS.get(code, '?'), 'suit': '',
            'color': TILE_COLORS['z'], 'red': False}


def action_tokens(label, lan=None):
    """Keep localized words and replace every Unicode tile with a stable tile.

    Match the localized name as well so red fives are not confused with normal
    fives (the old strings use the same Unicode character for both).
    """
    label = str(label)
    for key in ('PASS','CHI','PON','KAN','REACH','AGARI','RYUKYOKU'):
        label = label.replace(getattr(ActionUnicode, key), '')
    candidates = []
    for code, glyph in MJAI_TILE_2_UNICODE.items():
        suffix = lan.mjai2str(code) if lan else ''
        candidates.append((glyph + suffix, code))
    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)
    tokens, text, i = [], '', 0
    while i < len(label):
        match = next(((word, code) for word, code in candidates if label.startswith(word, i)), None)
        if match:
            if text:
                tokens.append({'text': text})
                text = ''
            tokens.append({'tile': tile_data(match[1])})
            i += len(match[0])
        else:
            text += label[i]
            i += 1
    if text:
        tokens.append({'text': text})
    tiles = [token for token in tokens if 'tile' in token]
    if len(tiles) == 1:
        plain = label
        for glyph in set(MJAI_TILE_2_UNICODE.values()):
            plain = plain.replace(glyph, '')
        return [tiles[0], {'text': ' ' + plain.strip()}]
    return tokens


def advice_rows(line, options, lan=None):
    matches = [i for i, (label, _) in enumerate(options) if line.endswith(label)]
    selected = matches[0] if len(matches) == 1 else -1
    rows = [{'label': line, 'tokens': action_tokens(line, lan),
             'weight': options[selected][1] if selected >= 0 else None, 'primary': True}]
    rows.extend({'label': label, 'tokens': action_tokens(label, lan), 'weight': weight,
                 'primary': False} for i, (label, weight) in enumerate(options) if i != selected)
    return rows
