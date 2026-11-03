# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Exercise actual native MJAI callbacks without weights, credentials or a game."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def check(native):
    assert native.consts.obs_shape(4)==(1012,34)
    assert native.consts.ACTION_SPACE==46
    class Engine:
        name = 'offline-release-check'
        engine_type = 'mortal'
        is_oracle = False
        version = 4
        enable_quick_eval = False
        enable_rule_based_agari_guard = False
        def react_batch(self,obs,masks,invisible_obs):
            assert obs[0].shape==native.consts.obs_shape(4)
            self.observed = True
            return ([int(np.flatnonzero(mask)[0]) for mask in masks],
                    [np.zeros(native.consts.ACTION_SPACE).tolist() for _ in masks],
                    [mask.tolist() for mask in masks],[True]*len(masks))
    for seat in range(4):
        hands = [['?']*13 for _ in range(4)]
        hands[seat] = ['1m','2m','3m','4m','5m','6m','7m','8m','9m','1p','2p','3p','4p']
        events = [{'type':'start_game','names':['offline']*4,'id':seat},
            {'type':'start_kyoku','bakaze':'E','dora_marker':'1s','kyoku':1,'honba':0,'kyotaku':0,
             'oya':seat,'scores':[25000]*4,'tehais':hands},
            {'type':'tsumo','actor':seat,'pai':'5p'}]
        engine = Engine()
        bot = native.mjai.Bot(engine,seat)
        for event in events:
            reaction = bot.react(json.dumps(event))
        assert engine.observed and json.loads(reaction)['type']=='dahai'
        assert json.loads(reaction)['actor']==seat
    return {'ok':True,'checks':['v4 observation shape','action space','all four seats',
                               'real MJAI inference callbacks','legal discard response']}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path)
    args = parser.parse_args()
    if args.library:
        spec = importlib.util.spec_from_file_location('libriichi',args.library.resolve())
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)
    else:
        try:
            import libriichi as native
        except ImportError:
            import riichi as native
    print(json.dumps(check(native)))
