"""Hardware-free sensor parsing, transaction, and exposure timing checks."""
import ast
import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / 'OT2_Server_2026-06-11'
spec = importlib.util.spec_from_file_location('uno_under_test', ROOT / 'lib/uno_control.py')
uno = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, serial=types.ModuleType('serial')):
    spec.loader.exec_module(uno)


class SensorTests(unittest.TestCase):
    def make_uno(self, replies):
        device = uno.Uno.__new__(uno.Uno)
        device._serial_lock = threading.Lock()
        device.board = Mock()
        device.board.readline.side_effect = replies
        return device

    def test_valid_readings_keep_existing_string_schema(self):
        device = self.make_uno([b'25.12,42.34\r\n'] * 2)
        expected = {'temperature': '25.12', 'humidity': '42.34'}
        self.assertEqual(device.read_temp_humidity(), expected)
        self.assertEqual(device.read_2nd_temp_humidity(), expected)
        self.assertEqual([c.args[0] for c in device.board.write.call_args_list], [b'S', b'T'])

    def test_invalid_readings_are_missing_without_retry(self):
        for raw in (b'25,40', b'', b'OK\n', b'x,y\n', b'nan,40\n',
                    b'25,inf\n', b'25,-1\n', b'25,101\n', b'131,40\n'):
            with self.subTest(raw=raw):
                device = self.make_uno([raw])
                self.assertIsNone(device.read_temp_humidity())
                self.assertEqual(device.board.write.call_count, 1)

    def test_firmware_errors_have_bounded_retries(self):
        with patch.object(uno.time, 'sleep'):
            device = self.make_uno([b'ERR,SHT31 read failed\n'] * 3)
            self.assertIsNone(device.read_2nd_temp_humidity())
            self.assertEqual(device.board.write.call_count, 3)
            device = self.make_uno([b'ERR,SHT31 read failed\n', b'25,40\n'])
            self.assertEqual(device.read_2nd_temp_humidity()['humidity'], '40')

    def test_transaction_holds_lock_for_write_and_read(self):
        device = self.make_uno([b'25,40\n'])
        device.board.write.side_effect = lambda _: self.assertTrue(device._serial_lock.locked())
        def read():
            self.assertTrue(device._serial_lock.locked())
            return b'25,40\n'
        device.board.readline.side_effect = read
        device.read_temp_humidity()
        self.assertFalse(device._serial_lock.locked())

    def test_reading_occurs_after_hover_wait_before_cap_moves(self):
        # Extract the actual method without importing/connecting the arm SDK.
        tree = ast.parse((ROOT / 'lib/arm.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'put_cap')
        events = []
        namespace = {'time': types.SimpleNamespace(sleep=lambda seconds: events.append(('wait', seconds)))}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<put_cap>', 'exec'), namespace)
        arm = Mock()
        arm.go_to_position.side_effect = lambda zone, position: events.append(('move', position))
        namespace['put_cap'](arm, 30, lambda: events.append(('read',)))
        self.assertEqual(events, [('move', 'cap waypoint'), ('move', 'cap hover'),
                                  ('wait', 30), ('read',), ('move', 'cap'), ('move', 'cap waypoint')])

    def test_protocol_reads_with_n2_on_and_stops_on_sensor_exception(self):
        tree = ast.parse((ROOT / 'protocol-multithreaded.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Name) and n.test.id == 'nitrogen')
        code = compile(ast.Module(body=[branch], type_ignores=[]), '<nitrogen>', 'exec')
        for fail in (False, True):
            with self.subTest(sensor_failure=fail):
                events = []
                device, arm = Mock(), Mock()
                device.start_blow.side_effect = lambda: events.append('on')
                device.stop_blow.side_effect = lambda: events.append('off')
                def read():
                    events.append('read')
                    if fail:
                        raise OSError('serial disconnected')
                    return {'temperature': '25', 'humidity': '40'}
                device.read_2nd_temp_humidity.side_effect = read
                def hover(seconds, on_hover_end):
                    events.append('hover')
                    on_hover_end()
                    events.append('place_cap')
                arm.put_cap.side_effect = hover
                namespace = dict(nitrogen=True, arduino=device, xArm=arm,
                                 coupon_to_bath_wait_time=30, parameters={})
                if fail:
                    with self.assertRaises(OSError):
                        exec(code, namespace)
                    self.assertEqual(events, ['on', 'hover', 'read', 'off'])
                else:
                    exec(code, namespace)
                    self.assertEqual(events, ['on', 'hover', 'read', 'place_cap', 'off'])
                    self.assertEqual(namespace['parameters']['coupon_air_data']['humidity'], '40')


if __name__ == '__main__':
    unittest.main()
