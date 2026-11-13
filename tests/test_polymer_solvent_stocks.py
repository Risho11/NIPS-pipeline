"""Real mass-balance functions, with robot calls replaced by mocks."""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/pipeline'))
import run_pareto_validation as runner

spec = importlib.util.spec_from_file_location('stock_calculations', ROOT / 'OT2_Server_2026-06-11/lib/calculations.py')
calc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = calc
spec.loader.exec_module(calc)


class PolymerSolventTests(unittest.TestCase):
    def test_actual_setup_supports_all_ten_recipes(self):
        setup = json.loads((ROOT / 'protocols/pareto_validation_setup.local.json').read_text())
        plan = runner.load_plan(runner.PLAN)
        for batch in plan['batches']:
            metadata = runner.validate_setup(batch, setup[batch['batch_id']])
            expected = 17 if batch['batch_id'].startswith('psf-') else 21
            self.assertEqual(metadata, {'stock_mode': 'polymer_solvent', 'polymer_stock_wt_percent': expected})
            for condition in batch['conditions']:
                params = condition['parameters']
                result = calc.calculate_batch(calc.TargetRecipe(1000, params['polymer_wt'], 0),
                                              calc.PolymerSolventStockParameters(expected), round_to_uL=False)
                self.assertAlmostEqual(result.final_polymer_wt_percent, params['polymer_wt'])
                self.assertAlmostEqual(result.polymer_stock_uL + result.solvent_uL, 1000)
                self.assertEqual(result.final_additive_wt_percent, 0)

    def test_direct_stock_and_rounded_dilution(self):
        for concentration in [17, 21]:
            stock = calc.PolymerSolventStockParameters(concentration)
            result = calc.calculate_batch(calc.TargetRecipe(1000, concentration, 0), stock)
            self.assertEqual((result.polymer_stock_uL, result.solvent_uL), (1000, 0))
            result = calc.calculate_batch(calc.TargetRecipe(1000, 14.5, 0), stock)
            self.assertAlmostEqual(result.total_volume_uL, 1000)
            self.assertLess(abs(result.final_polymer_wt_percent - 14.5), .03)
            for polymer, additive in [(concentration + 1, 0), (14.5, 1)]:
                with self.assertRaises(ValueError):
                    calc.calculate_batch(calc.TargetRecipe(1000, polymer, additive), stock)
        with self.assertRaises(ValueError):
            calc.calculate_batch(calc.TargetRecipe(1000, math.nan, 0), stock)

    def test_robot_uses_only_polymer_and_solvent_bottles(self):
        tree = ast.parse((ROOT / 'OT2_Server_2026-06-11/lib/ot2.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'OT2')
        names = ['update_metadata', 'get_stock_weight_percent', 'get_additive_percent',
                 'get_additive_polymer_percent', 'prepare_membrane_solution']
        functions = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = dict(calc=calc, np=types.SimpleNamespace(isfinite=math.isfinite),
                         solvent_slot_no=6, solvent_well_no=0, solution_slot_no=9, solution_well_no=0,
                         heater_slot_no=11, time=Mock())
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<stock methods>', 'exec'), namespace)
        Hardware = type('MockHardware', (), {name: namespace[name] for name in names})
        for target in [17, 14.5]:
            hardware = Hardware()
            hardware.bottle_inventory = Mock()
            hardware.heater_well_index = 0
            for name in ['attach_next_tip', 'prep_pullcast_asperate', '_drop', '_transfer', '_mix',
                         'prep_pullcast_from_mix_asperate']:
                setattr(hardware, name, Mock())
            hardware.has_temp = Mock(return_value=False)
            hardware.update_metadata({'stock_mode': 'polymer_solvent', 'polymer_stock_wt_percent': 17})
            self.assertEqual(hardware.get_stock_weight_percent(), 17)
            self.assertEqual(hardware.get_additive_percent(), 0)
            with redirect_stdout(io.StringIO()):
                hardware.prepare_membrane_solution(1000, target, 0, 25)
            required = hardware.bottle_inventory.require.call_args.args[0]
            self.assertTrue(set(required).issubset({'polymer_stock', 'solvent'}))
            if target == 17:
                hardware.prep_pullcast_asperate.assert_called_once_with(9, 0, 1000, True)
                hardware._transfer.assert_not_called()
            else:
                self.assertEqual([call.args[:2] for call in hardware._transfer.call_args_list], [(6, 0), (9, 0)])
                hardware._mix.assert_called_once()

    def test_existing_stock_modes_keep_their_calculation_paths(self):
        recipe = calc.TargetRecipe(1000, 17, 0)
        legacy = calc.calculate_batch(recipe, calc.LegacyStockParameters())
        four = calc.calculate_batch(recipe, calc.StockParameters())
        self.assertIsInstance(legacy, calc.LegacyMixingResult)
        self.assertIsInstance(four, calc.MixingResult)
        self.assertEqual(legacy.normal_polymer_stock_uL, 1000)
        self.assertEqual(legacy.polymer_additive_stock_uL, 0)
        self.assertEqual(four.polymer_stock_uL, 1000)


if __name__ == '__main__':
    unittest.main()
