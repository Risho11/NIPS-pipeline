# Browser camera streams

From the repository root:

```powershell
uv run python src/pipeline/camera_stream.py
```

Open http://127.0.0.1:5000 for a 2×2 view of cameras 0–3, matching
`src/pipeline/cameras.py`. Each camera has an MJPEG endpoint such as
http://127.0.0.1:5000/video_feed/0. Missing cameras display a placeholder
and retry every three seconds. Devices open when their stream is first requested
and remain open until the server exits. Stop with Ctrl+C.

Select cameras or change the resolution and frame rate for live streams
and recordings:

```powershell
uv run python src/pipeline/camera_stream.py --cameras 0 2 --width 1280 --height 720 --fps 10
```

The server listens on `0.0.0.0` by default, including the Tailscale and LAN
interfaces. From another device connected to your tailnet, open
`http://<camera-PC-Tailscale-IP>:5000`. Find that IP by running `tailscale ip -4`
on the camera PC. Tailscale access rules and the PC firewall must allow TCP
port 5000. For LAN access, use `http://<camera-PC-LAN-IP>:5000`.
This app has no authentication and also accepts connections through other
reachable network interfaces. To listen only locally, use `--host 127.0.0.1`.
Use one server process; its camera readers are shared by all connected viewers.
Keep the desktop `cameras.py` viewer closed: simultaneous access caused camera 0
to become unavailable. Camera 2 has worked with experiment capture and streaming
running together on this setup; no changes to `run_loop.py` are needed.

## Record each experiment automatically

On the pipeline PC, start the camera server in a separate terminal:

```powershell
uv run python src/pipeline/camera_stream.py
```

Run `run_loop.py` or `run_pareto_validation.py` as usual. Both use local port
5000 by default. If you start the camera server with a different `--port`, set
`NIPS_CAMERA_RECORDING_PORT` to match it in the experiment terminal:

```powershell
$env:NIPS_CAMERA_RECORDING_PORT = '5001'
```

The camera server saves to the repository's `recordings/` directory by default.
Use `--record-dir` to choose another location.
Recording requires FFmpeg with the `libx264` encoder on `PATH`. The browser
feeds and the recorded grid share the `--width`, `--height`, and `--fps`
settings, which default to 1920×1080 at 15 fps. The recorder rounds odd
dimensions up to the next even pixel for encoding. Each MP4 targets 2.5 Mb/s,
about 1.05 GiB per hour.
While FFmpeg is writing, the file ends in `.mp4.part`. The recorder publishes
the final `.mp4` name after FFmpeg finishes.

Automatic cleanup is enabled by default. Use `--no-cleanup-recordings`
to disable it. The default folder limit is 100 GiB and the default
free-space floor is 30 GiB. To choose other limits, set both flags as needed.

```powershell
uv run python src/pipeline/camera_stream.py --recordings-limit-gib 80 --min-free-space-gib 40
```

The server checks storage before starting each recording and every five seconds
while recording. It applies the folder limit and free-space floor to the
recording drive. When the project is on a different drive, it also checks the
project's free space. Cleanup deletes the oldest
readable MP4s in dated recording folders first, using file modification times.
Active `.mp4.part` files and other files count toward the folder limit.
If cleanup cannot make room, the server refuses to start the recording or
finalizes the one in progress and reports a warning. The live feeds continue.

The camera server waits for a recording request, even while viewers are
watching the stream. Each experiment starts one grid MP4 before submission.
The run loop stops recording on the matching completion
callback, and Pareto validation stops after the sample's completion check.
The pipeline logs the path as `yyyy-mm-dd/<sample name>.mp4`, relative to
`recordings/`. For example:

```text
recordings/
├── 2026-11-18/
│   ├── sample name.mp4
│   ├── sample name_run2.mp4
│   └── another sample.mp4
└── 2026-11-19/
    └── sample name.mp4
```

Each file contains one camera grid with cameras 0 and 1 on top and 2 and 3
below by default. Unavailable cameras appear as black tiles. Git ignores
the repository's `recordings/` directory. The folder uses the local date when
recording starts. Pareto validation uses its job name, and the run loop uses
the planned sample folder name. If a video already exists with that name
on the same day, the recorder adds a numbered `_run` suffix. The experiment
script prints a `[CAMERA WARNING]` if the server is unreachable, the MP4
writer fails, or no camera frames were captured. The experiment continues.
To disable this integration, set `$env:NIPS_CAMERA_RECORDING_PORT = 'off'`.

Both experiment scripts use camera 2 by default for measurement snapshots.
If the camera driver cannot share it, add `--reserved-camera 2` to the camera
server command. The grid keeps that quadrant black and the experiment script
retains access to the device. Use the configured snapshot camera index if it
differs from 2.

The local API accepts JSON POSTs at `/recording/<uuid>/start` and
`/recording/<uuid>/stop`. Use the same UUID for start and stop. The start
request accepts an optional `sample_name`, and both endpoints return a
`filename` relative to the recording directory. For example:

```powershell
$id = [guid]::NewGuid()
Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{"sample_name":"sample 1"}' -Uri "http://127.0.0.1:5000/recording/$id/start"
Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{}' -Uri "http://127.0.0.1:5000/recording/$id/stop"
```

To record the browser grid as a single video with OBS, open `http://127.0.0.1:5000` on the camera PC and press
F11 for fullscreen. The grid fits all four feeds within the browser window
without cropping. Capture that window with OBS and save recordings locally.
Remote viewers can use the Tailscale address at the same time. Local browser
traffic stays on the PC; remote viewing uses network bandwidth.
