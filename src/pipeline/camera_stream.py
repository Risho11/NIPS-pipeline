"""Stream USB cameras in a browser: python src/pipeline/camera_stream.py."""

import argparse
import atexit
import logging
import re
import shutil
import stat
import subprocess
import threading
import time
from datetime import datetime
from functools import partial
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, abort, render_template_string, request


RECORDING_WIDTH = 1920
RECORDING_HEIGHT = 1080
RECORDING_FPS = 15
GIB = 1024 ** 3
RECORDINGS_LIMIT = 100 * GIB
MIN_FREE_SPACE = 30 * GIB
STORAGE_CHECK_INTERVAL = 5
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class VideoRecording:
    def __init__(self, path, partial_path, ffmpeg, width, height, fps):
        self.path = path
        self.partial_path = partial_path
        self.fps = fps
        self.failed = False
        self.has_camera_frames = False
        self.storage_error = None
        windows_process_group = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        self.process = subprocess.Popen([
            ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
            '-f', 'rawvideo', '-pixel_format', 'bgr24',
            '-video_size', f'{width}x{height}',
            '-framerate', str(fps), '-i', 'pipe:0',
            '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-threads', '2',
            '-b:v', '2500k', '-maxrate', '3M', '-bufsize', '6M',
            '-pix_fmt', 'yuv420p', '-f', 'mp4', str(partial_path),
        ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            creationflags=windows_process_group, start_new_session=not windows_process_group)

    def write(self, frame):
        try:
            self.process.stdin.write(memoryview(frame).cast('B'))
        except OSError as error:
            logging.error('Recording stopped for %s: %s', self.path, error)
            self.failed = True

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            self.failed = True
        try:
            status = self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            self.failed = True
            logging.error('FFmpeg did not finalize %s in time', self.path)
            return
        if status:
            self.failed = True
            logging.error('FFmpeg exited with status %d for %s', status, self.path)
        if self.failed:
            return
        try:
            if not self.partial_path.stat().st_size or self.path.exists():
                raise OSError('Cannot publish MP4 to the final path')
            self.partial_path.rename(self.path)
        except OSError as error:
            self.failed = True
            logging.error('Could not finalize %s: %s', self.path, error)


def is_link(info):
    return (stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def check_recording_storage(directory, recordings_limit, min_free_space):
    if (directory.stat().st_dev != PROJECT_ROOT.stat().st_dev
            and shutil.disk_usage(PROJECT_ROOT).free <= min_free_space):
        raise OSError(f'The experiment drive needs more than {min_free_space / GIB:g} GiB free')

    folders = [directory]
    total = 0
    completed = []
    while folders:
        for path in folders.pop().iterdir():
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if is_link(info):
                continue
            if stat.S_ISDIR(info.st_mode):
                folders.append(path)
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                if (path.suffix.lower() == '.mp4' and path.parent.parent == directory
                        and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.parent.name)):
                    completed.append((info.st_mtime_ns, path, info))

    for _, path, info in sorted(completed):
        if total < recordings_limit and shutil.disk_usage(directory).free > min_free_space:
            return
        # Legacy recordings used the final name while open. Require a readable
        # video stream so an unfinished legacy MP4 is also protected.
        if path.parent.resolve() != path.parent:
            continue
        video = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
        try:
            playable = video.isOpened()
        finally:
            video.release()
        if not playable:
            continue
        try:
            current = path.lstat()
            if (path.parent.resolve() != path.parent or is_link(current)
                    or not stat.S_ISREG(current.st_mode)
                    or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                    != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)):
                continue
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as error:
            logging.warning('Could not remove old recording %s: %s', path, error)
            continue
        total -= info.st_size
        logging.warning('Removed old recording %s to reclaim space', path)

    if total >= recordings_limit or shutil.disk_usage(directory).free <= min_free_space:
        raise OSError(f'Recording storage needs less than {recordings_limit / GIB:g} GiB in the folder '
                      f'and more than {min_free_space / GIB:g} GiB free')


class CameraStream:
    """One capture worker per device, shared by all browser connections."""

    def __init__(self, index, width=RECORDING_WIDTH, height=RECORDING_HEIGHT,
                 fps=RECORDING_FPS, record_grid_frames=False):
        self.index = index
        self.width, self.height, self.fps = width, height, fps
        self.condition = threading.Condition()
        self.stop_event = threading.Event()
        self.thread = None
        self.jpeg = None
        self.sequence = 0
        self.record_grid_frames = record_grid_frames
        self.latest_frame = None

    def start(self):
        with self.condition:
            if self.thread is None and not self.stop_event.is_set():
                self.thread = threading.Thread(target=self._capture, daemon=True)
                self.thread.start()

    def _capture(self):
        camera = None
        retry_at = 0
        try:
            while not self.stop_event.is_set():
                started = time.monotonic()
                frame = None
                try:
                    if camera is None and started >= retry_at:
                        camera = cv2.VideoCapture(self.index)
                        camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    if camera is not None:
                        ok, frame = camera.read()
                        if not ok or frame is None:
                            camera.release()
                            camera = None
                            frame = None
                            retry_at = started + 3
                except cv2.error:
                    if camera is not None:
                        camera.release()
                    camera = None
                    frame = None
                    retry_at = started + 3

                captured = frame is not None
                if not captured:
                    frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    cv2.putText(frame, f"Camera {self.index} unavailable", (20, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                if self.index in (0, 1):
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                if self.record_grid_frames:
                    with self.condition:
                        self.latest_frame = frame if captured else None
                ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    with self.condition:
                        self.jpeg = encoded.tobytes()
                        self.sequence += 1
                        self.condition.notify_all()
                self.stop_event.wait(max(0, 1 / self.fps - (time.monotonic() - started)))
        finally:
            if camera is not None:
                camera.release()
            self.stop_event.set()
            with self.condition:
                self.condition.notify_all()

    def frames(self):
        self.start()
        previous = 0
        while not self.stop_event.is_set():
            with self.condition:
                self.condition.wait_for(
                    lambda: self.sequence != previous or self.stop_event.is_set())
                if self.stop_event.is_set():
                    return
                previous, jpeg = self.sequence, self.jpeg
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')

    def close(self):
        self.stop_event.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread is not None:
            self.thread.join(timeout=2)


def record_grid(cameras, recording, grid, tile_width, tile_height, stop_event, check_storage):
    next_check = time.monotonic() + STORAGE_CHECK_INTERVAL
    try:
        while True:
            started = time.monotonic()
            if check_storage is not None and started >= next_check:
                try:
                    check_storage()
                except OSError as error:
                    recording.storage_error = str(error)
                    logging.warning('Stopping recording %s: %s', recording.path, error)
                    break
                next_check = time.monotonic() + STORAGE_CHECK_INTERVAL
            grid.fill(0)
            for position, camera in enumerate(cameras):
                if camera is None:
                    continue
                with camera.condition:
                    frame = camera.latest_frame
                if frame is None:
                    continue
                recording.has_camera_frames = True
                row, column = divmod(position, 2)
                frame_height, frame_width = frame.shape[:2]
                scale = min(tile_width / frame_width, tile_height / frame_height)
                scaled_width = max(1, round(frame_width * scale))
                scaled_height = max(1, round(frame_height * scale))
                x = column * tile_width + (tile_width - scaled_width) // 2
                y = row * tile_height + (tile_height - scaled_height) // 2
                grid[y:y + scaled_height, x:x + scaled_width] = cv2.resize(
                    frame, (scaled_width, scaled_height))
            recording.write(grid)
            if recording.failed or stop_event.wait(max(0, 1 / recording.fps -
                                                       (time.monotonic() - started))):
                break
    except (cv2.error, OSError) as error:
        recording.failed = True
        logging.error('Could not record %s: %s', recording.path, error)
    finally:
        recording.close()


class GridRecorder:
    def __init__(self, directory, cameras, width, height, fps, *, cleanup,
                 recordings_limit, min_free_space):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cameras = cameras
        self.width = width + width % 2
        self.height = height + height % 2
        self.fps = fps
        self.check_storage = (partial(check_recording_storage, self.directory,
                                      recordings_limit, min_free_space) if cleanup else None)
        self.lock = threading.Lock()
        self.active = None

    def start(self, owner, sample_name=None):
        if sample_name is not None and (
            not isinstance(sample_name, str) or not sample_name
            or sample_name != sample_name.strip(' .')
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', sample_name)
            or Path(sample_name + '.mp4').is_reserved()
        ):
            raise ValueError('Sample name must be a valid filename stem')
        with self.lock:
            if self.active is not None:
                active_owner, recording, _, _ = self.active
                if active_owner != owner:
                    raise ValueError('Another recording is active')
                return recording.path.relative_to(self.directory).as_posix()
            ffmpeg = shutil.which('ffmpeg')
            if ffmpeg is None:
                raise OSError('FFmpeg with libx264 is required for recording')

            started = datetime.now()
            day = self.directory / started.strftime('%Y-%m-%d')
            day.mkdir(exist_ok=True)
            if is_link(day.lstat()):
                raise OSError(f'Recording date directory is a link: {day}')
            if self.check_storage is not None:
                self.check_storage()
            for camera in self.cameras:
                if camera is not None:
                    camera.start()
            tile_width = self.width // 2
            tile_height = self.height // max(2, (len(self.cameras) + 1) // 2)
            grid = np.zeros((self.height, self.width, 3), dtype=np.uint8)

            stem = sample_name or started.strftime('%Y-%m-%d %H-%M-%S')
            run = 1
            while True:
                path = day / (f'{stem}.mp4' if run == 1 else f'{stem}_run{run}.mp4')
                partial_path = path.with_suffix('.mp4.part')
                run += 1
                if path.exists() or path.is_symlink():
                    continue
                try:
                    partial_path.touch(exist_ok=False)
                except FileExistsError:
                    continue
                if path.exists() or path.is_symlink():
                    partial_path.unlink()
                    continue
                break
            try:
                recording = VideoRecording(path, partial_path, ffmpeg, self.width, self.height, self.fps)
            except OSError as error:
                partial_path.unlink(missing_ok=True)
                raise OSError(f'Could not start MP4 recording: {error}') from error
            stop = threading.Event()
            worker = threading.Thread(target=record_grid,
                                      args=(self.cameras, recording, grid, tile_width,
                                            tile_height, stop, self.check_storage))
            try:
                worker.start()
            except RuntimeError as error:
                recording.failed = True
                recording.close()
                partial_path.unlink(missing_ok=True)
                raise OSError(f'Could not start recording worker: {error}') from error
            self.active = owner, recording, stop, worker
            return path.relative_to(self.directory).as_posix()

    def stop(self, owner=None):
        with self.lock:
            if self.active is None:
                return None
            active_owner, recording, stop, worker = self.active
            if owner is not None and active_owner != owner:
                raise ValueError('Another recording is active')
            stop.set()
            worker.join()
            self.active = None
            if recording.failed:
                recording.partial_path.unlink(missing_ok=True)
                raise OSError('Recording did not produce a playable file')
            if recording.storage_error is not None:
                raise OSError(f'Recording ended early: {recording.storage_error}. '
                              f'Saved {recording.path.relative_to(self.directory).as_posix()}')
            if not recording.has_camera_frames:
                raise OSError(f'No camera frames were captured in {recording.path.name}')
            return recording.path.relative_to(self.directory).as_posix()


PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live cameras</title>
<style>
* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
body { background: black; color: #eee; font-family: sans-serif; }
main { display: grid; width: 100%; height: 100%;
       grid-template-columns: repeat(2, minmax(0, 1fr));
       grid-template-rows: repeat({{ (cameras|length + 1) // 2 }}, minmax(0, 1fr)); }
figure { position: relative; margin: 0; min-width: 0; min-height: 0; }
img { display: block; width: 100%; height: 100%; object-fit: contain; }
figcaption { position: absolute; bottom: 8px; left: 8px; padding: 4px 8px;
             background: rgba(0, 0, 0, 0.6); border-radius: 4px; }
</style></head>
<body><main>
{% for index in cameras %}
<figure><img src="{{ url_for('video_feed', camera_id=index) }}" alt="Camera {{ index }}">
<figcaption>Camera {{ index }}</figcaption></figure>
{% endfor %}
</main></body></html>"""


def create_app(camera_indices=(0, 1, 2, 3), width=RECORDING_WIDTH, height=RECORDING_HEIGHT,
               fps=RECORDING_FPS, record_dir=None, reserved_camera=None, *,
               cleanup_recordings=True, recordings_limit=RECORDINGS_LIMIT,
               min_free_space=MIN_FREE_SPACE):
    if width <= 0 or height <= 0 or not 0 < fps <= 120:
        raise ValueError('Width and height must be positive; FPS must be between 0 and 120.')
    app = Flask(__name__)
    camera_indices = tuple(dict.fromkeys(camera_indices))
    cameras = {
        index: CameraStream(index, width, height, fps, record_dir is not None)
        for index in camera_indices
        if index != reserved_camera
    }
    app.extensions['camera_streams'] = cameras
    recorder = None if record_dir is None else GridRecorder(
        record_dir, [cameras.get(index) for index in camera_indices], width, height, fps,
        cleanup=cleanup_recordings, recordings_limit=recordings_limit, min_free_space=min_free_space)
    app.extensions['grid_recorder'] = recorder
    for camera in cameras.values():
        atexit.register(camera.close)

    @app.get('/')
    def index():
        return render_template_string(PAGE, cameras=cameras)

    @app.get('/video_feed/<int:camera_id>')
    def video_feed(camera_id):
        if camera_id not in cameras:
            abort(404)
        return Response(cameras[camera_id].frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame',
                        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @app.post('/recording/<uuid:owner>/<action>')
    def control_recording(owner, action):
        if recorder is None or action not in ('start', 'stop'):
            abort(404)
        if request.remote_addr not in ('127.0.0.1', '::1'):
            abort(403)
        if not request.is_json:
            abort(415)
        body = request.get_json()
        if not isinstance(body, dict):
            abort(400)
        try:
            filename = (recorder.start(owner, body.get('sample_name')) if action == 'start'
                        else recorder.stop(owner))
        except ValueError as error:
            return {'error': str(error)}, 409
        except OSError as error:
            app.logger.error('Recording %s failed: %s', action, error)
            return {'error': str(error)}, 500
        return {'filename': filename}

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--cameras', type=int, nargs='+', default=[0, 1, 2, 3])
    parser.add_argument('--width', type=int, default=RECORDING_WIDTH,
                        help='Live feed and recording width in pixels (default: %(default)s).')
    parser.add_argument('--height', type=int, default=RECORDING_HEIGHT,
                        help='Live feed and recording height in pixels (default: %(default)s).')
    parser.add_argument('--fps', type=float, default=RECORDING_FPS,
                        help='Live feed and recording frame rate (default: %(default)s).')
    parser.add_argument('--record-dir', type=Path,
                        default=PROJECT_ROOT / 'recordings',
                        help='Save each camera grid MP4 in a dated subdirectory (default: repository recordings/).')
    parser.add_argument('--cleanup-recordings', action=argparse.BooleanOptionalAction, default=True,
                        help='Delete oldest completed MP4s when a storage limit is reached (enabled by default).')
    parser.add_argument('--recordings-limit-gib', type=int, default=RECORDINGS_LIMIT // GIB,
                        help='Maximum recording folder size for cleanup in GiB (default: %(default)s).')
    parser.add_argument('--min-free-space-gib', type=int, default=MIN_FREE_SPACE // GIB,
                        help='Minimum free drive space for cleanup in GiB (default: %(default)s).')
    parser.add_argument('--record-on-demand', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--reserved-camera', type=int,
                        help='Keep this camera available for pipeline snapshots.')
    args = parser.parse_args()
    if args.recordings_limit_gib <= 0 or args.min_free_space_gib < 0:
        parser.error('The folder limit must be positive and minimum free space must be nonnegative.')
    app = create_app(args.cameras, args.width, args.height, args.fps, args.record_dir,
                     args.reserved_camera, cleanup_recordings=args.cleanup_recordings,
                     recordings_limit=args.recordings_limit_gib * GIB,
                     min_free_space=args.min_free_space_gib * GIB)
    cameras = app.extensions['camera_streams']
    recorder = app.extensions['grid_recorder']
    try:
        # Reloading or multiple processes would open the same devices twice.
        app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    finally:
        try:
            if recorder is not None:
                recorder.stop()
        except OSError as error:
            app.logger.warning('Camera recording could not be finalized: %s', error)
        finally:
            for camera in cameras.values():
                camera.close()


if __name__ == '__main__':
    main()
