import unittest
from common.presentation import annotate_advice_groups


class AdviceGroupTests(unittest.TestCase):
    def rows(self,weights):
        return annotate_advice_groups([{'label':str(i),'weight':w,'primary':i==0} for i,w in enumerate(weights)])

    def test_one_clear_leader_keeps_primary_accent(self):
        rows=self.rows([.82,.10,.04])
        self.assertEqual([r['emphasis'] for r in rows],[True,False,False])
        self.assertTrue(rows[0]['leading'])
        self.assertEqual([r['divider_before'] for r in rows],[False,True,False])

    def test_two_close_choices_move_divider_after_both(self):
        rows=self.rows([.46,.43,.07])
        self.assertEqual([r['emphasis'] for r in rows],[True,True,False])
        self.assertFalse(any(r['leading'] for r in rows))
        self.assertEqual([r['divider_before'] for r in rows],[False,False,True])

    def test_three_close_choices_have_no_divider(self):
        rows=self.rows([.34,.33,.30])
        self.assertTrue(all(r['emphasis'] for r in rows))
        self.assertFalse(any(r['leading'] or r['divider_before'] for r in rows))

    def test_threshold_uses_percentage_points_and_inclusive_boundary(self):
        self.assertTrue(self.rows([.40,.35,.20])[1]['emphasis'])
        self.assertFalse(self.rows([.40,.349,.20])[1]['emphasis'])

    def test_relative_guard_does_not_group_half_as_likely_action(self):
        self.assertFalse(self.rows([.08,.04,.03])[1]['emphasis'])

    def test_candidates_compare_with_top_not_previous_neighbor(self):
        self.assertEqual([r['emphasis'] for r in self.rows([.40,.36,.32])],[True,True,False])

    def test_randomized_lower_action_is_not_promoted_or_reordered(self):
        rows=self.rows([.20,.67,.08])
        self.assertEqual([r['weight'] for r in rows],[.20,.67,.08])
        self.assertEqual([r['emphasis'] for r in rows],[True,False,False])
        self.assertFalse(any(r['leading'] for r in rows))

    def test_missing_invalid_and_zero_weights_keep_regular_grouping(self):
        for weights in ([None,.46,.43],[0,0,0],[float('nan'),.4,.3],[float('inf'),.4,.3],[True,.4,.3]):
            with self.subTest(weights=weights):
                rows=self.rows(weights)
                self.assertEqual([r['emphasis'] for r in rows],[True,False,False])
                self.assertFalse(any(r['leading'] for r in rows))

    def test_annotation_does_not_mutate_inference_data(self):
        original=[{'weight':.46,'primary':True},{'weight':.43,'primary':False}]
        result=annotate_advice_groups(original)
        self.assertEqual(original,[{'weight':.46,'primary':True},{'weight':.43,'primary':False}])
        self.assertIsNot(result[0],original[0])

    def test_empty_and_single_candidate_have_no_empty_separator(self):
        self.assertEqual(annotate_advice_groups([]),[])
        self.assertFalse(self.rows([.8])[0]['divider_before'])


if __name__=='__main__':
    unittest.main()
