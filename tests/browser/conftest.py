"""Fixtures for the browser tests.

These drive a real Chromium against a real server, because the things they
cover cannot be reached any other way: ES module wiring, the data-action
dispatcher, Leaflet rendering, websocket updates arriving in a live page, and
CSS layout at a given window size. None of that is visible to the API tests.

The server runs in a thread inside the pytest process, so it shares the same
state module the fixtures reset -- seeding goes over HTTP anyway, to exercise
the real path and the broadcasts that come with it.
"""
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from main import app


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """A real uvicorn on a free port, for the duration of the session."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("server did not start within 15s")
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def api(live_server):
    """HTTP client against the live server, for seeding and assertions."""
    with httpx.Client(base_url=live_server, timeout=10) as c:
        yield c


@pytest.fixture
def seeded(api):
    """A small fixed scenario with arithmetic that is easy to assert on.

    Statuses are chosen so the sector wheels land on round numbers:
    power 0% (two Compromised), medical 100% (two Clean), financial 70%
    (one Monitored). The threshold then fires on power and not on the others.
    """
    pins = [
        ("Rosslyn Substation", "Power Plants", "Compromised", "Offline"),
        ("Pepco Substation",   "Power Plants", "Compromised", "Critical"),
        ("Childrens National", "Hospitals",    "Clean",       "Healthy"),
        ("GW Hospital",        "Hospitals",    "Clean",       "Healthy"),
        ("Industrial Bank",    "Banks",        "Monitored",   "Healthy"),
    ]
    created = {}
    for i, (name, cat, status, op) in enumerate(pins):
        r = api.post("/api/pins", json={
            "name": name, "category": cat, "status": status, "op_status": op,
            "lat": 38.90 + i * 0.01, "lon": -77.03 - i * 0.01,
        })
        assert r.status_code == 201, r.text
        created[name] = r.json()["id"]

    api.post("/api/edges", json={
        "from_pid": created["Rosslyn Substation"],
        "to_pid": created["Childrens National"],
        "label": "primary feed",
    }).raise_for_status()

    api.post("/api/thresholds", json={
        "name": "Grid critical", "sector": "power",
        "below_pct": 50, "severity": "critical",
    }).raise_for_status()

    return created


@pytest.fixture
def app_page(page, live_server):
    """A loaded page that fails the test on any uncaught JS error.

    Silent breakage is the failure mode that matters here -- a module that
    does not resolve, or a handler that throws, leaves a page that looks
    almost right. Collecting errors and asserting on them is the point.
    """
    errors = []

    def _is_noise(text):
        # Chromium logs a console error for every non-2xx response. A request
        # the server was meant to reject is not an uncaught JS error, and
        # neither is the websocket closing as the page tears down.
        return "WebSocket" in text or "Failed to load resource" in text

    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(f"console.error: {m.text}")
            if m.type == "error" and not _is_noise(m.text) else None)

    # The window run.py opens. Several panels sit off-screen at narrower
    # widths, and the SITREP strip has its own breakpoint below 1360px.
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function("() => document.querySelectorAll('[data-action]').length > 0")
    page.errors = errors
    yield page
    assert not errors, f"uncaught JS errors: {errors}"


@pytest.fixture
def right_panel(app_page):
    """Open the slide-in right panel.

    It is parked at right:-270px until opened, so the timer, map lock and
    markup tools inside it are genuinely outside the viewport and cannot be
    clicked. Tests that need them ask for this fixture.
    """
    app_page.click("#tools-btn")
    app_page.wait_for_selector("#right-panel.open")
    return app_page

def pytest_collection_modifyitems(config, items):
    """Skip these rather than erroring when the browser is not installed.

    `pip install -r requirements-dev.txt` gets the Python package, but the
    Chromium binary needs `playwright install chromium` on top. Without that,
    a plain `pytest` should still run the API suite and say why the rest were
    skipped.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return
    except Exception as exc:
        reason = f"chromium unavailable ({type(exc).__name__}); run: playwright install chromium"

    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if "tests/browser/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip)
