import builtins
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'OT2_Server_2026-06-11' / 'armtest.py'

class CapOnlyTest(unittest.TestCase):
    def run_mode(self, answer):
        calls = []
        class FakeArm:
            def __init__(self, **kwargs):
                calls.append(('init', kwargs))
            def open_gripper(self):
                calls.append(('open_gripper',))
            def pick_up(self, item):
                calls.append(('pick_up', item))
            def put_down(self, item):
                calls.append(('put_down', item))
        module = types.ModuleType('arm')
        module.Arm = FakeArm
        # Empty inventory must not prevent this isolated transfer.
        robot = dict(coupons=0, rings=0, discard=0, camera_box_open=True)
        from io import StringIO
        with patch.dict(sys.modules, arm=module), \
             patch.object(sys, 'argv', [str(SCRIPT), '--cap-bath-to-stand']), \
             patch.object(builtins, 'input', return_value=answer), \
             patch.object(builtins, 'open', return_value=StringIO(json.dumps(robot))), \
             patch.object(sys, 'path', list(sys.path)):
            with self.assertRaises(SystemExit) as result:
                exec(compile(SCRIPT.read_text(), str(SCRIPT), 'exec'), {'__name__': '__main__'})
        self.assertEqual(result.exception.code, 0)
        return calls

    def test_only_cap_transfer(self):
        self.assertEqual(self.run_mode('y'), [
            ('init', {
                'coupons': 0, 'rings': 0, 'discards': 0,
                'camera_box_open': True, 'home': False,
                'initialize': False, 'current_zone': 'opentrons',
            }),
            ('pick_up', 'cap bath'), ('put_down', 'cap stand'),
        ])

    def test_cancel_before_connection(self):
        self.assertEqual(self.run_mode('n'), [])

if __name__ == '__main__':
    unittest.main()
