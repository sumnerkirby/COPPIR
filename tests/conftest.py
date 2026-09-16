"""Shared fixtures.

The app keeps all its state in module-level dicts in main.py, so every test
has to start from a clean slate or results depend on execution order. The
reset fixture is autouse for that reason.
"""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    """Empty the in-memory state and point scenario writes at a temp dir.

    Without the SCENARIOS_DIR redirect, tests that save scenarios would write
    into the working copy next to the real ones.
    """
    for store in (main.pins, main.injects, main.edges):
        store.clear()
    for store in (main.thresholds, main.decision_log):
        del store[:]

    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    monkeypatch.setattr(main, "SCENARIOS_DIR", scenarios)
    yield scenarios


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def make_pin(client):
    """Create a pin and hand back its JSON, so tests are not full of boilerplate."""
    def _make(**overrides):
        body = {"name": "Test Asset", "category": "Asset", "lat": 38.9, "lon": -77.03}
        body.update(overrides)
        r = client.post("/api/pins", json=body)
        assert r.status_code == 201, r.text
        return r.json()
    return _make
