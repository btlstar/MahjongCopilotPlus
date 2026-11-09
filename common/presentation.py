# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Tile/action presentation shared by desktop and in-game advice."""
import re
import math
from numbers import Real
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


def annotate_advice_groups(rows):
    """Emphasize nearby top policies without reordering the selected action.

    Compare each candidate with the maximum, never with its previous neighbor.
    A randomized lower-ranked action or unknown weight keeps the old grouping.
    """
    if not rows:
        return []
    def weight(row):
        value = row.get('weight')
        return float(value) if isinstance(value,Real) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=1 else None
    weights = [weight(row) for row in rows]
    valid = [value for value in weights if value is not None]
    maximum = max(valid,default=0)
    top = weights[0] is not None and maximum>0 and abs(weights[0]-maximum)<=1e-9
    count = 1
    if top:
        for value in weights[1:3]:
            if value is None or maximum-value>0.05+1e-9 or value+1e-9<maximum*0.85:
                break
            count += 1
    return [dict(row,emphasis=index<count,leading=top and count==1 and index==0,
                 divider_before=index==count) for index,row in enumerate(rows)]


def advice_rows(line, options, lan=None):
    # A riichi-and-discard label ends with a tile too, but that tile's policy
    # describes discarding *without* riichi. Only match the complete action,
    # with a narrow compatibility case for plain discard tile labels.
    matches = [i for i, (label, _) in enumerate(options) if line == label]
    if not matches:
        discard = lan.DISCARD if lan else 'Discard'
        matches = [i for i, (label, _) in enumerate(options) if line == discard + label]
    selected = matches[0] if len(matches) == 1 else -1
    rows = [{'label': line, 'tokens': action_tokens(line, lan),
             'weight': options[selected][1] if selected >= 0 else None, 'primary': True}]
    rows.extend({'label': label, 'tokens': action_tokens(label, lan), 'weight': weight,
                 'primary': False} for i, (label, weight) in enumerate(options) if i != selected)
    return annotate_advice_groups(rows)
