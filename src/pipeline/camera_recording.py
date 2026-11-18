"""Best-effort control of the local camera stream recorder."""

import json
import os
import urllib.error
import urllib.request


def recording_port():
    port = os.environ.get('NIPS_CAMERA_RECORDING_PORT', '5000').strip()
    return None if port.lower() == 'off' else port


def control_recording(action, owner, *, sample_name=None):
    port = recording_port()
    if not port:
        return
    try:
        if not 1 <= int(port) <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        url = f'http://127.0.0.1:{int(port)}/recording/{owner}/{action}'
        body = {} if sample_name is None else {'sample_name': sample_name}
        request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            filename = json.load(response)['filename']
        if filename:
            print(f'[CAMERA] Recording {action}: {filename}', flush=True)
    except urllib.error.HTTPError as error:
        with error:
            try:
                reason = json.load(error)['error']
            except (OSError, ValueError, KeyError, TypeError):
                reason = str(error)
        print(f'[CAMERA WARNING] Recording {action} failed: {reason}', flush=True)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'[CAMERA WARNING] Recording {action} failed: {error}', flush=True)
