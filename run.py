#!/usr/bin/env python3
"""
COPPIR desktop launcher.
Opens a native pywebview window with the loading screen immediately,
starts the FastAPI server as a subprocess, then navigates once ready.
"""
import sys, subprocess, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).parent

import webview  # fast import — native window opens in < 1s

PORT  = 8000
URL   = f'http://localhost:{PORT}'
_proc = None

LOADING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #000a00;
  font-family: 'Courier New', Courier, monospace;
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.brand {
  font-size: 52px;
  font-weight: bold;
  color: #00ff41;
  letter-spacing: 14px;
}
.line {
  font-size: 10px;
  color: #336633;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-align: center;
  line-height: 2;
}
.first { margin-top: 16px; }
.bar-wrap {
  width: 220px;
  height: 2px;
  background: #001400;
  margin-top: 34px;
  border-radius: 1px;
  overflow: hidden;
}
.bar {
  height: 100%;
  width: 30%;
  background: #00ff41;
  border-radius: 1px;
  animation: sweep 1.4s ease-in-out infinite;
}
@keyframes sweep {
  0%   { transform: translateX(-110%); }
  100% { transform: translateX(460%); }
}
.status {
  font-size: 10px;
  color: #336633;
  letter-spacing: 3px;
  margin-top: 18px;
  text-transform: uppercase;
}
</style>
</head>
<body>
  <div class="brand">COPPIR</div>
  <div class="line first">Common Operational Picture</div>
  <div class="line">Program for Incident Response</div>
  <div class="bar-wrap"><div class="bar"></div></div>
  <div class="status">Starting server&#8230;</div>
</body>
</html>"""


def _server_ready():
    try:
        urllib.request.urlopen(URL, timeout=0.8)
        return True
    except Exception:
        return False


def _on_start(window):
    """Called by pywebview in a background thread once the GUI loop is running."""
    global _proc

    if getattr(sys, 'frozen', False):
        # Frozen build: sys.executable is the bundle itself, not a Python
        # interpreter, so subprocess + '-m uvicorn' cannot work. Run the
        # server in a daemon thread inside the same process instead.
        import asyncio, uvicorn
        from main import app as _app

        if sys.platform == 'win32':
            # Python 3.8+ on Windows defaults to ProactorEventLoop which
            # conflicts with some libraries; SelectorEventLoop is safer.
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        _t = threading.Thread(
            target=lambda: uvicorn.run(
                _app, host='127.0.0.1', port=PORT, log_level='warning'),
            daemon=True,
        )
        _t.start()
        while not _server_ready():
            time.sleep(0.3)
    else:
        # Development: launch uvicorn as a subprocess so code changes are
        # picked up without rebuilding.
        _proc = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'main:app',
             '--host', '127.0.0.1', f'--port={PORT}', '--log-level', 'warning'],
            cwd=str(HERE),
        )
        while not _server_ready():
            if _proc.poll() is not None:
                break
            time.sleep(0.3)

    window.load_url(URL)


if __name__ == '__main__':
    window = webview.create_window(
        'COPPIR — Common Operational Picture Program for Incident Response',
        html=LOADING_HTML,
        width=1440,
        height=900,
        min_size=(1100, 700),
    )
    webview.start(_on_start, window, debug=False)

    if _proc and _proc.poll() is None:
        _proc.terminate()
