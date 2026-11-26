import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np

from src.pipeline import camera_stream


class CameraRecordingTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name).resolve()

    def file(self, relative_path, size, modified):
        path = self.directory / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'0' * size)
        os.utime(path, (modified, modified))
        return path

    def test_cleanup_removes_oldest_playable_recording_first(self):
        unfinished = self.file('2026-11-18/bad.mp4', 10, 100)
        oldest = self.file('2026-11-18/old.mp4', 10, 200)
        newer = self.file('2026-11-19/new.mp4', 10, 300)
        active = self.file('2026-11-19/in-progress.mp4.part', 10, 100)
        unrelated = self.file('archive/other.mp4', 10, 100)

        def open_video(path, backend):
            return SimpleNamespace(isOpened=lambda: Path(path) != unfinished,
                                   release=lambda: None)

        with (patch.object(camera_stream.shutil, 'disk_usage',
                           return_value=SimpleNamespace(free=100)),
              patch.object(camera_stream.cv2, 'VideoCapture', side_effect=open_video)):
            camera_stream.check_recording_storage(self.directory, 45, 0)

        self.assertFalse(oldest.exists())
        self.assertTrue(all(path.exists() for path in (unfinished, newer, active, unrelated)))

    def test_cleanup_protects_active_file_when_free_space_cannot_be_recovered(self):
        old = self.file('2026-11-18/old.mp4', 10, 100)
        active = self.file('2026-11-19/in-progress.mp4.part', 10, 200)
        video = SimpleNamespace(isOpened=lambda: True, release=lambda: None)

        with (patch.object(camera_stream.shutil, 'disk_usage',
                           return_value=SimpleNamespace(free=20)),
              patch.object(camera_stream.cv2, 'VideoCapture', return_value=video)):
            with self.assertRaisesRegex(OSError, '32 GiB free'):
                camera_stream.check_recording_storage(
                    self.directory, camera_stream.RECORDINGS_LIMIT, 32 * camera_stream.GIB)

        self.assertFalse(old.exists())
        self.assertTrue(active.exists())

    def test_default_cleanup_checks_storage_before_starting_cameras_or_encoder(self):
        with (patch.object(camera_stream.shutil, 'which', return_value='ffmpeg'),
              patch.object(camera_stream.CameraStream, 'start') as start_camera,
              patch.object(camera_stream.VideoRecording, '__init__') as start_encoder,
              patch.object(camera_stream, 'check_recording_storage',
                           side_effect=OSError('free space is low')) as check_storage):
            app = camera_stream.create_app((0,), record_dir=self.directory)
            response = app.test_client().post(f'/recording/{uuid4()}/start', json={})
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json['error'], 'free space is low')
            check_storage.assert_called_once_with(
                self.directory, 100 * camera_stream.GIB, 30 * camera_stream.GIB)
            start_camera.assert_not_called()
            start_encoder.assert_not_called()

    def test_command_line_passes_shared_settings_and_cleanup_options(self):
        app = Mock(extensions={'camera_streams': {}, 'grid_recorder': None})
        args = ['camera_stream.py', '--width', '640', '--height', '480', '--fps', '12.5',
                '--record-dir', str(self.directory), '--recordings-limit-gib', '80',
                '--min-free-space-gib', '40', '--no-cleanup-recordings']
        with (patch.object(sys, 'argv', args),
              patch.object(camera_stream, 'create_app', return_value=app) as create_app):
            camera_stream.main()
        create_app.assert_called_once_with(
            [0, 1, 2, 3], 640, 480, 12.5, self.directory, None, cleanup_recordings=False,
            recordings_limit=80 * camera_stream.GIB, min_free_space=40 * camera_stream.GIB)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),
                         'FFmpeg and ffprobe are required for the encoding test')
    def test_h264_recording_uses_the_preview_dimensions_and_frame_rate(self):
        app = camera_stream.create_app((0, 1), 640, 480, 12.5, self.directory,
                                       cleanup_recordings=False)
        recorder = app.extensions['grid_recorder']
        self.addCleanup(recorder.stop)
        for camera in app.extensions['camera_streams'].values():
            self.assertEqual((camera.width, camera.height, camera.fps), (640, 480, 12.5))
            camera.latest_frame = np.full((48, 64, 3), 128, dtype=np.uint8)

        owner = uuid4()
        endpoint = f'/recording/{owner}'
        frame_written = threading.Event()
        write = camera_stream.VideoRecording.write

        def write_frame(recording, frame):
            write(recording, frame)
            frame_written.set()

        with (app.test_client() as client,
              patch.object(camera_stream.CameraStream, 'start'),
              patch.object(camera_stream.VideoRecording, 'write', write_frame),
              patch.object(camera_stream, 'check_recording_storage') as check_storage):
            response = client.post(f'{endpoint}/start', json={'sample_name': 'sample'})
            self.assertEqual(response.status_code, 200, response.json)
            path = self.directory / response.json['filename']
            self.assertTrue(frame_written.wait(timeout=10))
            self.assertTrue(path.with_suffix('.mp4.part').exists())
            self.assertFalse(path.exists())
            response = client.post(f'{endpoint}/stop', json={})
            self.assertEqual(response.status_code, 200, response.json)
            check_storage.assert_not_called()

        self.assertFalse(path.with_suffix('.mp4.part').exists())
        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,width,height,avg_frame_rate', '-of', 'json', str(path),
        ], capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(json.loads(probe.stdout)['streams'], [
            {'codec_name': 'h264', 'width': 640, 'height': 480, 'avg_frame_rate': '25/2'},
        ])

    def test_active_recorder_finalizes_when_periodic_storage_check_fails(self):
        class Recording:
            path = self.directory / '2026-11-18' / 'sample.mp4'
            failed = False
            storage_error = None
            closed = False

            def write(self, frame):
                pass

            def close(self):
                self.closed = True

        recording = Recording()
        grid = np.zeros((2, 2, 3), dtype=np.uint8)
        with (patch.object(camera_stream, 'STORAGE_CHECK_INTERVAL', 0),
              patch.object(camera_stream, 'check_recording_storage',
                           side_effect=OSError('free space is low')) as check_storage):
            camera_stream.record_grid([], recording, grid, 1, 1, threading.Event(), check_storage)

        self.assertTrue(recording.closed)
        self.assertFalse(recording.failed)
        self.assertEqual(recording.storage_error, 'free space is low')
