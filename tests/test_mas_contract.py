"""Operational contracts with synthetic conditions only; no SDK or device calls."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
from mas_contract import (Conditions, Context, Decision, MainReply, Materials,
                          installed_stocks, validate_conditions)

PARAMS = dict(mixing_temp=50, bath_temp=7, pullcast_speed=6, nitrogen=True,
              coupon_to_bath_wait_time=250, nips_bath_wait_time=1600,
              polymer_wt=16, additive_wt=0)
CONTEXT = dict(campaign='synthetic', objective='Improve E and F without invented weights',
               materials=dict(polymer_type='synthetic-polymer', solvent_type='synthetic-solvent',
                              cosolvent_type='none', nips_bath_solvent='synthetic-solvent',
                              nips_bath_solvent_wt_percent=10),
               stock_metadata=dict(stock_mode='two_bottle', polymer_stock_wt_percent=17,
                                   additive_stock_polymer_wt_percent=17,
                                   additive_stock_additive_wt_percent=4),
               locked_additive_wt=0)
PARAMS = Conditions.model_validate(PARAMS).model_dump()
CONTEXT = Context.model_validate(CONTEXT).model_dump()


class ContractTests(unittest.TestCase):
    def test_point_segment_stocks_reject_impossible_compositions(self):
        for stock in [dict(stock_mode='two_bottle', polymer_stock_wt_percent=0,
                           additive_stock_polymer_wt_percent=0, additive_stock_additive_wt_percent=0),
                      dict(stock_mode='two_bottle', polymer_stock_wt_percent=17,
                           additive_stock_polymer_wt_percent=17, additive_stock_additive_wt_percent=0),
                      dict(stock_mode='four_bottle', polymer_stock_pwt=17,
                           solvents_cswt=0, all_mix_pwt=17, all_mix_cswt=0)]:
            with self.subTest(stock=stock), self.assertRaises(ValueError):
                context = Context.model_validate(dict(CONTEXT, stock_metadata=stock))
                validate_conditions(dict(PARAMS, polymer_wt=90), context)

    def test_arbitrary_stock_hulls_support_points_segments_and_nonwinding_vertices(self):
        cases = [
            (dict(stock_mode='two_bottle', polymer_stock_wt_percent=0,
                  additive_stock_polymer_wt_percent=0, additive_stock_additive_wt_percent=0),
             [(0, 0)], [(0.01, 0), (0, 0.01)]),
            (dict(stock_mode='four_bottle', polymer_stock_pwt=0,
                  solvents_cswt=0, all_mix_pwt=0, all_mix_cswt=0),
             [(0, 0)], [(0.01, 0), (0, 0.01)]),
            (dict(stock_mode='two_bottle', polymer_stock_wt_percent=17,
                  additive_stock_polymer_wt_percent=17, additive_stock_additive_wt_percent=0),
             [(0, 0), (8.5, 0), (17, 0)], [(17.01, 0), (8, 0.01)]),
            (dict(stock_mode='two_bottle', polymer_stock_wt_percent=0,
                  additive_stock_polymer_wt_percent=6, additive_stock_additive_wt_percent=4),
             [(0, 0), (3, 2), (6, 4)], [(9, 6), (3, 2.1), (3, 1.9)]),
            (dict(stock_mode='four_bottle', polymer_stock_pwt=0,
                  solvents_cswt=4, all_mix_pwt=0, all_mix_cswt=2),
             [(0, 0), (0, 2), (0, 4)], [(0.01, 2), (0, 4.1)]),
            (dict(stock_mode='four_bottle', polymer_stock_pwt=17,
                  solvents_cswt=30, all_mix_pwt=2, all_mix_cswt=3),
             [(0, 0), (17, 0), (0, 30), (8.5, 15), (2, 3)], [(17, 30), (9, 15)]),
        ]
        for stock, feasible, impossible in cases:
            original = copy.deepcopy(stock)
            context = Context.model_validate(dict(CONTEXT, stock_metadata=stock, locked_additive_wt=None))
            for p, a in feasible:
                with self.subTest(stock=stock, feasible=(p, a)):
                    values = dict(PARAMS, mixing_temp=25, polymer_wt=p, additive_wt=a)
                    accepted = validate_conditions(values, context)
                    self.assertEqual((accepted.polymer_wt, accepted.additive_wt), (p, a))
            for p, a in impossible:
                with self.subTest(stock=stock, impossible=(p, a)), self.assertRaisesRegex(ValueError, 'polygon'):
                    validate_conditions(dict(PARAMS, mixing_temp=25, polymer_wt=p, additive_wt=a), context)
            self.assertEqual(stock, original)

    def test_strict_finite_conditions_and_operator_context(self):
        context = Context.model_validate(CONTEXT)
        self.assertEqual(validate_conditions(PARAMS, context).model_dump(), PARAMS)
        for bad in [dict(PARAMS, bath_temp=True), dict(PARAMS, polymer_wt=float('nan')),
                    dict(PARAMS, nitrogen='true'), dict(PARAMS, extra=1),
                    {k: v for k, v in PARAMS.items() if k != 'mixing_temp'}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Conditions.model_validate(bad)
        with self.assertRaises(ValueError):
            Materials.model_validate(dict(CONTEXT['materials'], nips_bath_solvent_wt_percent=float('inf')))
        with self.assertRaises(ValueError):
            Conditions.model_validate(dict(PARAMS, polymer_type='changed'))

    def test_polygon_lock_and_undiluted_stock_never_project(self):
        context = Context.model_validate(CONTEXT)
        for bad in [dict(PARAMS, additive_wt=1), dict(PARAMS, polymer_wt=18),
                    dict(PARAMS, polymer_wt=17), dict(PARAMS, bath_temp=26)]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_conditions(bad, context)
        self.assertEqual(validate_conditions(dict(PARAMS, polymer_wt=17, mixing_temp=25), context).polymer_wt, 17)
        unlocked = context.model_copy(update={'locked_additive_wt': None})
        with self.assertRaisesRegex(ValueError, 'polygon'):
            validate_conditions(dict(PARAMS, polymer_wt=1, additive_wt=4), unlocked)

    def test_explicit_stock_metadata_and_composition_totals(self):
        for stock in [{}, {'stock_mode': 'two_bottle'},
                      dict(CONTEXT['stock_metadata'], additive_stock_polymer_wt_percent=99),
                      dict(CONTEXT['stock_metadata'], polymer_stock_wt_percent=True),
                      dict(CONTEXT['stock_metadata'], polymer_stock_wt_percent='17')]:
            with self.subTest(stock=stock), self.assertRaises(ValueError):
                installed_stocks(stock)
        four = dict(stock_mode='four_bottle', polymer_stock_pwt=20, solvents_cswt=30,
                    all_mix_pwt=20, all_mix_cswt=40)
        self.assertEqual(installed_stocks(four).all_mix_cswt, 40)
        with self.assertRaisesRegex(ValueError, '100'):
            installed_stocks(dict(four, all_mix_cswt=90))
        # Input objects are not silently adjusted.
        original = copy.deepcopy(CONTEXT)
        Context.model_validate(CONTEXT)
        self.assertEqual(CONTEXT, original)

    def test_run_hold_stop_and_no_old_taxonomy(self):
        for action in ['run', 'hold', 'stop']:
            payload = dict(action=action, reason='synthetic', knowledge_commit='commit',
                           next_params=PARAMS if action == 'run' else None)
            decision = Decision.model_validate(payload)
            self.assertEqual(decision.action, action)
            with self.assertRaises(ValueError):
                Decision.model_validate(dict(payload, next_params=None if action == 'run' else PARAMS))
        with self.assertRaises(ValueError):
            MainReply.model_validate(dict(knowledge=None, design=None, decision=None, records=[], hypotheses=[]))
        with self.assertRaises(ValueError):
            MainReply.model_validate(dict(knowledge=None, design=None,
                decision=dict(action='run', next_params=PARAMS, reason='unreviewed', knowledge_commit='x'), records=[]))
        reply = MainReply.model_validate(dict(knowledge=None, design=None,
            decision=dict(action='hold', next_params=None, reason='Need evidence', knowledge_commit='x'), records=[]))
        self.assertIsNone(reply.design)


if __name__ == '__main__':
    unittest.main()
