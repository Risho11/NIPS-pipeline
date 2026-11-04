# Browser camera streams

From the repository root:

```powershell
python -m pip install Flask opencv-python numpy
python src/pipeline/camera_stream.py
```

Open http://127.0.0.1:5000 for a 2×2 view of cameras 0–3, matching
`src/pipeline/cameras.py`. Each camera has an MJPEG endpoint such as
http://127.0.0.1:5000/video_feed/0. Missing cameras display a placeholder
and retry every three seconds. Devices open when their stream is first requested
and remain open until the server exits. Stop with Ctrl+C.

Select cameras or reduce resolution and frame rate:

```powershell
python src/pipeline/camera_stream.py --cameras 0 2 --width 1280 --height 720 --fps 10
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

For local OBS recording, open `http://127.0.0.1:5000` on the camera PC and press
F11 for fullscreen. The grid fits all four feeds within the browser window
without cropping. Capture that window with OBS and save recordings locally.
Remote viewers can use the Tailscale address at the same time. Local browser
traffic stays on the PC; remote viewing uses network bandwidth.
