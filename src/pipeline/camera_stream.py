"""Stream USB cameras in a browser: python src/pipeline/camera_stream.py."""

import argparse
import atexit
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, abort, render_template_string, request


class VideoRecording:
    def __init__(self, path, fps, size):
        self.path = path
        self.fps = fps
        self.failed = False
        self.has_camera_frames = False
        self.writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        if not self.writer.isOpened():
            self.close()
            raise OSError('Could not open MP4 writer')

    def write(self, frame):
        if self.failed:
            return
        try:
            self.writer.write(frame)
        except (cv2.error, OSError) as error:
            logging.error('Recording stopped for %s: %s', self.path, error)
            self.failed = True
            self.close()

    def close(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None


class CameraStream:
    """One capture worker per device, shared by all browser connections."""

    def __init__(self, index, width=1920, height=1080, fps=15, record_grid_frames=False):
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


def record_grid(cameras, recording, grid, tile_width, tile_height, stop_event):
    try:
        while True:
            started = time.monotonic()
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
    finally:
        recording.close()


class GridRecorder:
    def __init__(self, directory, cameras, width, height, fps):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cameras = cameras
        self.width, self.height, self.fps = width, height, fps
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
            started = datetime.now()
            day = self.directory / started.strftime('%Y-%m-%d')
            day.mkdir(exist_ok=True)
            stem = sample_name or started.strftime('%Y-%m-%d %H-%M-%S')
            path = day / f'{stem}.mp4'
            run = 2
            while True:
                try:
                    path.touch(exist_ok=False)
                    break
                except FileExistsError:
                    path = day / f'{stem}_run{run}.mp4'
                    run += 1
            for camera in self.cameras:
                if camera is not None:
                    camera.start()
            tile_width, tile_height = (self.width + 1) // 2, (self.height + 1) // 2
            height = ((len(self.cameras) + 1) // 2) * tile_height
            # OpenCV's MP4 encoder needs even dimensions.
            grid = np.zeros((height + height % 2, 2 * tile_width, 3), dtype=np.uint8)
            try:
                recording = VideoRecording(path, self.fps, (grid.shape[1], grid.shape[0]))
            except (cv2.error, OSError) as error:
                path.unlink(missing_ok=True)
                raise OSError(f'Could not start MP4 recording: {error}') from error
            stop = threading.Event()
            worker = threading.Thread(target=record_grid,
                                      args=(self.cameras, recording, grid, tile_width,
                                            tile_height, stop))
            worker.start()
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
            if recording.failed or not recording.path.stat().st_size:
                recording.path.unlink()
                raise OSError('Recording did not produce a playable file')
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


def create_app(camera_indices=(0, 1, 2, 3), width=1920, height=1080, fps=15,
               record_dir=None, reserved_camera=None):
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
        record_dir, [cameras.get(index) for index in camera_indices], width, height, fps)
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
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--fps', type=float, default=15)
    parser.add_argument('--record-dir', type=Path,
                        help='Save each camera grid MP4 in a dated subdirectory.')
    parser.add_argument('--record-on-demand', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--reserved-camera', type=int,
                        help='Keep this camera available for pipeline snapshots.')
    args = parser.parse_args()
    if args.record_on_demand and args.record_dir is None:
        parser.error('--record-on-demand requires --record-dir')
    app = create_app(args.cameras, args.width, args.height, args.fps, args.record_dir,
                     args.reserved_camera)
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
