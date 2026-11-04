"""Stream USB cameras in a browser: python src/pipeline/camera_stream.py."""

import argparse
import atexit
import threading
import time

import cv2
import numpy as np
from flask import Flask, Response, abort, render_template_string


class CameraStream:
    """One capture worker per device, shared by all browser connections."""

    def __init__(self, index, width=1920, height=1080, fps=15):
        self.index = index
        self.width, self.height, self.fps = width, height, fps
        self.condition = threading.Condition()
        self.stop_event = threading.Event()
        self.thread = None
        self.jpeg = None
        self.sequence = 0

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

                if frame is None:
                    frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    cv2.putText(frame, f"Camera {self.index} unavailable", (20, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
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


def create_app(camera_indices=(0, 1, 2, 3), width=1920, height=1080, fps=15):
    if width <= 0 or height <= 0 or not 0 < fps <= 120:
        raise ValueError('Width and height must be positive; FPS must be between 0 and 120.')
    app = Flask(__name__)
    cameras = {index: CameraStream(index, width, height, fps) for index in camera_indices}
    app.extensions['camera_streams'] = cameras
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

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--cameras', type=int, nargs='+', default=[0, 1, 2, 3])
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--fps', type=float, default=15)
    args = parser.parse_args()
    app = create_app(args.cameras, args.width, args.height, args.fps)
    try:
        # Reloading or multiple processes would open the same devices twice.
        app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    finally:
        for camera in app.extensions['camera_streams'].values():
            camera.close()


if __name__ == '__main__':
    main()
