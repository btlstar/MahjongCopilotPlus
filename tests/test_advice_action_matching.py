"""Match advice percentages to decisions, including two-stage riichi."""
from copy import deepcopy
import unittest
from bot_manager import mjai_reaction_2_guide
from common.lan_str import LanStr, LanStrZHS
from common.mj_helper import ActionUnicode, MJAI_TILE_2_UNICODE
from common.presentation import advice_rows


class AdviceActionMatchingTests(unittest.TestCase):
    def reaction(self, options=None):
        return {'type':'reach','actor':0,
                'meta_options':options if options is not None else [('reach',1.0),('5p',0.0),('8m',0.0)],
                'reach_dahai':{'type':'dahai','actor':0,'pai':'5p',
                               'meta_options':[('5p',.73),('8m',.27)]}}

    def render(self, reaction, lan=None):
        lan = lan or LanStrZHS()
        line, options = mjai_reaction_2_guide(reaction,3,lan)
        return line, options, advice_rows(line,options,lan)

    def test_riichi_uses_riichi_probability_instead_of_zero_discard(self):
        line, options, rows = self.render(self.reaction())
        self.assertEqual([r['weight'] for r in rows],[1.0,0.0,0.0])
        self.assertEqual(options[0][0],line)
        self.assertEqual(sum(LanStrZHS().RIICHI in r['label'] for r in rows),1)
        self.assertTrue(rows[0]['leading'])

    def test_followup_probability_does_not_replace_or_multiply_riichi_policy(self):
        _, _, rows = self.render(self.reaction([('reach',.8),('5p',.15),('8m',.05)]))
        self.assertEqual([r['weight'] for r in rows],[.8,.15,.05])

    def test_lower_rank_selected_riichi_keeps_its_own_weight(self):
        _, _, rows = self.render(self.reaction([('5p',.9),('reach',.1),('8m',0.0)]))
        self.assertEqual([r['weight'] for r in rows],[.1,.9,0.0])
        self.assertFalse(rows[0]['leading'])

    def test_missing_riichi_weight_does_not_borrow_discard_weight(self):
        _, _, rows = self.render(self.reaction([('5p',.9),('8m',.1)]))
        self.assertIsNone(rows[0]['weight'])
        self.assertEqual([r['weight'] for r in rows[1:]],[.9,.1])

    def test_legacy_compound_label_cannot_match_only_its_tile_suffix(self):
        lan = LanStrZHS()
        tile = MJAI_TILE_2_UNICODE['5p'] + lan.mjai2str('5p')
        line = ActionUnicode.REACH + lan.RIICHI + ',' + lan.DISCARD + tile
        rows = advice_rows(line,[(tile,0.0),(lan.RIICHI,1.0)],lan)
        self.assertIsNone(rows[0]['weight'])

    def test_english_and_red_five_keep_the_correct_action_identity(self):
        for lan in (LanStr(),LanStrZHS()):
            with self.subTest(language=lan.LANGUAGE_NAME):
                reaction = self.reaction([('reach',.95),('5pr',.04),('5p',.01)])
                reaction['reach_dahai']['pai'] = '5pr'
                line, _, rows = self.render(reaction,lan)
                self.assertEqual(rows[0]['weight'],.95)
                self.assertEqual(next(t['tile']['code'] for t in rows[0]['tokens'] if 'tile' in t),'5pr')
                self.assertEqual(sum(r['label']==line for r in rows),1)

    def test_presentation_never_changes_model_reaction(self):
        reaction = self.reaction()
        original = deepcopy(reaction)
        self.render(reaction)
        self.assertEqual(reaction,original)


if __name__=='__main__':
    unittest.main()
