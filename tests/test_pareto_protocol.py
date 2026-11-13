"""Mock-only validation protocol checks. Never imports or contacts robot hardware."""

import ast
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'pipeline'))
import run_pareto_validation as runner

spec = importlib.util.spec_from_file_location('compression_plan', ROOT / 'OT2_Server_2026-06-11/lib/compression_plan.py')
compression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compression)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.plan = runner.load_plan(runner.PLAN)
        self.batch = self.plan['batches'][0]

    def test_exact_reviewed_parameters_and_thirty_independent_samples(self):
        jobs = [job for batch in self.plan['batches'] for job in runner.jobs_for_batch(batch)]
        self.assertEqual(len(jobs), 30)
        self.assertEqual(self.plan['compression_test_locations'], ['coupon test 2', 'coupon test 4'])
        self.assertEqual(sum(len(batch['conditions']) for batch in self.plan['batches']), 10)
        for batch in self.plan['batches']:
            for selected in batch['conditions']:
                original = ROOT / selected['source_params']
                recorded = json.loads(original.read_text(encoding='utf-8'))
                self.assertEqual(selected['parameters'], {k: recorded[k] for k in selected['parameters']})
                self.assertEqual(sorted(job['repeat'] for job in jobs if job['condition'] is selected), [1, 2, 3])

    def test_preview_has_no_network_camera_or_state_access(self):
        with patch.object(runner.robot, 'check_health') as health, \
             patch.object(runner.robot, 'run_test') as submit, \
             patch.object(runner, 'Campaign') as campaign, redirect_stdout(io.StringIO()):
            runner.main(['--batch', 'psf-water'])
        health.assert_not_called()
        submit.assert_not_called()
        campaign.assert_not_called()

    def test_three_repeats_finish_before_advancing_condition(self):
        jobs = runner.jobs_for_batch(self.batch)
        expected = [(condition['validation_id'], repeat)
                    for condition in self.batch['conditions'] for repeat in (1, 2, 3)]
        self.assertEqual([(job['condition']['validation_id'], job['repeat']) for job in jobs], expected)
        self.assertEqual([job['condition']['validation_id'] for job in jobs],
                         ['V1'] * 3 + ['V2'] * 3 + ['V4'] * 3 + ['V5'] * 3)

    def test_legacy_four_locations_and_bottom_only_validation(self):
        self.assertEqual(compression.resolve_test_locations(), compression.LEGACY_LOCATIONS)
        self.assertEqual(compression.resolve_test_locations(['coupon test 2', 'coupon test 4']), compression.BOTTOM_LOCATIONS)
        for bad in [[], ['coupon test 1', 'coupon test 2'], ['coupon test 2'] * 2]:
            with self.assertRaises(ValueError):
                compression.resolve_test_locations(bad)

    def test_bottom_pair_tracks_casting_direction_and_coupon_rotation(self):
        # Read calibrated constants with AST; importing arm.py would contact an SDK.
        tree = ast.parse((ROOT / 'OT2_Server_2026-06-11/lib/arm.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'positions' for t in n.targets))
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<calibration constants>', 'exec'), namespace)
        positions = namespace['positions']
        self.assertGreater(positions['opentrons']['pullcast start pulldown'][0],
                           positions['opentrons']['pullcast end pulldown'][0])
        self.assertEqual(positions['opentrons']['coupon angled'][5], -90)
        self.assertEqual(positions['tester']['coupon flat'][5], 91)
        self.assertEqual([positions['tester'][name][0] for name in compression.BOTTOM_LOCATIONS], [170, 170])
        self.assertEqual([positions['tester'][f'coupon test {i}'][0] for i in [1, 3]], [160, 160])

    def test_real_compression_function_uses_two_locations_per_phase(self):
        tree = ast.parse((ROOT / 'OT2_Server_2026-06-11/protocol-multithreaded.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_compression_tests')
        arm, arduino, api = Mock(), Mock(), Mock()
        api.get_compressiontester_status.return_value = {'safe': True, 'age': 1, 'time': 0, 'current time': 1}
        arduino.run_test.return_value = True
        namespace = dict(tests=list(compression.LEGACY_LOCATIONS), xArm=arm, arduino=arduino,
                         url=api, compressionTesterLock=Mock(), armLock=Mock(), time=Mock(), sys=Mock())
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<compression function>', 'exec'), namespace)
        with redirect_stdout(io.StringIO()):
            namespace['run_compression_tests'](compression.BOTTOM_LOCATIONS)  # blank phase
            namespace['run_compression_tests'](compression.BOTTOM_LOCATIONS)  # membrane phase
        self.assertEqual(arduino.run_test.call_count, 4)
        self.assertEqual([call.args[0] for call in arm.put_down.call_args_list], list(compression.BOTTOM_LOCATIONS) * 2)
        # Verify run_test threads receive this sample's immutable location tuple.
        source = ast.unparse(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_test'))
        self.assertIn('args=(run_locations,)', source)
        self.assertIn('run_compression_tests(run_locations)', source)

    def setup_metadata(self, concentration=21):
        return dict(material_context=self.batch['material_context'], stock_metadata=dict(
            stock_mode='two_bottle', polymer_stock_wt_percent=concentration,
            additive_stock_polymer_wt_percent=17, additive_stock_additive_wt_percent=4))

    def test_actual_stock_feasibility_checked_without_recipe_clamping(self):
        before = copy.deepcopy(self.batch)
        runner.validate_setup(self.batch, self.setup_metadata())
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            runner.validate_setup(self.batch, self.setup_metadata(10))
        wrong = self.setup_metadata()
        wrong['material_context'] = dict(wrong['material_context'], solvent_type='wrong')
        with self.assertRaisesRegex(ValueError, 'material/bath'):
            runner.validate_setup(self.batch, wrong)
        with self.assertRaisesRegex(ValueError, 'stock_metadata'):
            runner.validate_setup(self.batch, dict(material_context=self.batch['material_context']))
        self.assertEqual(self.batch, before)

    def test_heated_undiluted_stock_is_rejected_without_rewriting_temperature(self):
        batch = copy.deepcopy(next(b for b in self.plan['batches'] if b['batch_id'] == 'primospire-water'))
        setup = self.setup_metadata(19)
        setup['material_context'] = batch['material_context']
        with self.assertRaisesRegex(ValueError, 'skips heated mixing'):
            runner.validate_setup(batch, setup)

    def make_campaign(self, tmp, collect_only=False):
        raw = Path(tmp) / 'newton'
        raw.mkdir(exist_ok=True)
        args = types.SimpleNamespace(campaign='test-pareto', test_locations=[2, 4],
                                     csv_raw_path=raw, robot_url='http://mock-robot',
                                     server_ip='127.0.0.1', server_port=8000, camera_index=2,
                                     collect_only=collect_only, sample_timeout=30)
        return runner.Campaign(self.plan, self.batch, self.setup_metadata(), args)

    def test_file_boundary_rejects_changed_old_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / 'old.csv'
            old.write_text('old')
            baseline = runner.csv_snapshot(root)
            fresh = root / 'fresh.csv'
            fresh.write_text('new')
            self.assertEqual(runner.new_csv_files(root, baseline), [fresh])
            old.write_text('modified old')
            with self.assertRaisesRegex(RuntimeError, 'Pre-existing'):
                runner.new_csv_files(root, baseline)

    def test_resume_keeps_sample_id_and_baseline_and_rejects_changed_configuration(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'ROOT', Path(tmp)):
            campaign = self.make_campaign(tmp)
            specification = runner.jobs_for_batch(self.batch)[0]
            job = campaign.prepare_job(specification, 0)
            resumed = self.make_campaign(tmp)
            self.assertEqual(resumed.prepare_job(specification, 0), job)
            self.assertEqual(len(resumed.state['jobs']), 1)
            with self.assertRaisesRegex(ValueError, 'configuration changed'):
                self.make_campaign(tmp, collect_only=True)
            altered = dict(job['payload'], mixing_temp=999)
            with self.assertRaisesRegex(ValueError, 'Callback'):
                resumed.receive_callback({'parameters': altered})

    def test_mock_batch_collects_only_four_new_files_and_stops_after_three_repeats(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'ROOT', Path(tmp)), \
             patch.object(runner.robot, 'check_health') as health, \
             patch.object(runner.robot, 'run_test') as submit, \
             patch.object(runner.Campaign, 'wait_for_completion'), \
             patch.object(runner, 'process_sample') as process, redirect_stdout(io.StringIO()):
            campaign = self.make_campaign(tmp)
            health.return_value = dict(journal_id=str(uuid.uuid4()), request_status_version=1, **compression.CAPABILITIES)
            old = campaign.args.csv_raw_path / 'unrelated.csv'
            old.write_text('older unrelated measurement')
            def physical_mock(payload, request_id, journal_id):
                self.assertEqual(payload['validation_request_id'], request_id)
                saved = json.loads(campaign.state_path.read_text())
                self.assertEqual(saved['jobs'][-1]['request_id'], request_id)
                job = campaign.current_job()
                number = len(campaign.state['jobs']) * 10
                for i in range(4):
                    (campaign.args.csv_raw_path / f'Specimen_{number+i}_11122026_12000{i}.csv').write_text(f'curve {number+i}')
                folder = Path(tmp) / 'data' / 'raw' / job['name']
                for name in ['before.jpg', 'after.jpg']:
                    (folder / name).write_bytes(b'mocked image')
                job['snapshots'] = ['before.jpg', 'after.jpg']
                campaign.receive_callback({'parameters': copy.deepcopy(payload), 'protocol_log': ['mocked']})
            submit.side_effect = physical_mock
            process.side_effect = RuntimeError('mocked analysis interruption')
            with self.assertRaisesRegex(RuntimeError, 'analysis interruption'):
                campaign.run()
            self.assertEqual(submit.call_count, 1)
            self.assertEqual(campaign.state['jobs'][0]['status'], 'collected')
            original_id = campaign.state['jobs'][0]['request_id']
            process.side_effect = None
            process.reset_mock()
            campaign = self.make_campaign(tmp)
            campaign.run()
            expected = len(self.batch['conditions']) * 3
            self.assertEqual(submit.call_count, expected)
            self.assertEqual(process.call_count, expected)
            self.assertTrue(campaign.state['completed'])
            self.assertEqual(campaign.state['jobs'][0]['request_id'], original_id)
            for job in campaign.state['jobs']:
                directory = Path(tmp) / 'data' / 'raw' / job['name']
                self.assertEqual(len(list(directory.glob('*.csv'))), 4)
                self.assertFalse((directory / 'unrelated.csv').exists())
                self.assertEqual(job['payload']['compression_test_locations'], ['coupon test 2', 'coupon test 4'])
            # Reopening the completed campaign submits no additional physical job.
            self.make_campaign(tmp).run()
            self.assertEqual(submit.call_count, expected)

    def test_legacy_robot_capabilities_rejected_before_submission(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'ROOT', Path(tmp)), \
             patch.object(runner.robot, 'check_health', return_value={'journal_id': str(uuid.uuid4())}), \
             patch.object(runner.robot, 'run_test') as submit:
            campaign = self.make_campaign(tmp)
            with self.assertRaisesRegex(RuntimeError, 'Deploy updated'):
                campaign.run()
            submit.assert_not_called()

    def test_request_status_is_read_only_and_advertises_capability(self):
        spec = importlib.util.spec_from_file_location('pareto_requests', ROOT / 'OT2_Server_2026-06-11/lib/request_server.py')
        requests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(requests)
        with tempfile.TemporaryDirectory() as tmp:
            journal = requests.RequestJournal(Path(tmp) / 'journal.json')
            request_id = str(uuid.uuid4())
            journal.data['requests'][request_id] = dict(status='completed', digest='saved-digest')
            before = copy.deepcopy(journal.data)
            handler = object.__new__(requests.make_handler(journal, Mock(), compression.CAPABILITIES))
            handler._reply = Mock()
            handler.path = '/health'
            handler.do_GET()
            self.assertEqual(handler._reply.call_args.args[1]['compression_row_pairs'], [['coupon test 2', 'coupon test 4']])
            handler.path = '/requests/' + request_id
            handler.do_GET()
            self.assertEqual(handler._reply.call_args.args[1]['status'], 'completed')
            self.assertEqual(handler._reply.call_args.args[1]['digest'], 'saved-digest')
            self.assertEqual(journal.data, before)

    def test_completion_requires_matching_robot_digest_and_callback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'ROOT', Path(tmp)):
            campaign = self.make_campaign(tmp)
            job = campaign.prepare_job(runner.jobs_for_batch(self.batch)[0], 0)
            campaign.state['journal_id'] = str(uuid.uuid4())
            status = dict(journal_id=campaign.state['journal_id'], digest=runner.digest(job['payload']), status='completed')
            def response():
                return io.BytesIO(json.dumps(status).encode())
            with patch.object(runner.urllib.request, 'urlopen', side_effect=lambda *a, **k: response()):
                with self.assertRaisesRegex(RuntimeError, 'without a recorded callback'):
                    campaign.wait_for_completion(job)
                campaign.receive_callback({'parameters': job['payload']})
                campaign.wait_for_completion(job)
                status['digest'] = 'changed'
                with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                    campaign.wait_for_completion(job)

    def test_existing_pairing_accepts_two_zero_and_two_membrane_files(self):
        # Exercise the actual chronological pairing helper, without fitting fake curves.
        import matplotlib
        matplotlib.use('Agg')
        import curve_segmentation as curves
        with tempfile.TemporaryDirectory() as tmp:
            condition = Path(tmp) / 'data/raw/two-location-sample'
            condition.mkdir(parents=True)
            (condition / 'params.json').write_text(json.dumps({'nips_bath_wait_time': 1800}))
            for index, stamp in enumerate(['120000', '120500', '130000', '130500'], 1):
                (condition / f'Specimen_{index}_11122026_{stamp}.csv').touch()
            pairs = curves.load_zero_sample_pairs_by_condition('data/raw', tmp, strict=True,
                                                               condition_filter=condition.name)
            self.assertEqual(pairs[condition.name]['num_pairs'], 2)
            self.assertEqual([p['zero_specimen'] for p in pairs[condition.name]['pairs']], [1, 2])
            self.assertEqual([p['sample_specimen'] for p in pairs[condition.name]['pairs']], [3, 4])


if __name__ == '__main__':
    unittest.main()
