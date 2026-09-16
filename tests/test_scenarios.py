"""Scenario save/load/delete, filename sanitising, and the state reset."""
import json

import pytest


@pytest.fixture
def populated(client, make_pin):
    """A session with something in every store, so round-trips are meaningful."""
    a = make_pin(name="Substation", category="Power Plants", status="Compromised")
    b = make_pin(name="Hospital", category="Hospitals")
    client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"],
                                    "label": "primary feed"})
    client.post("/api/injects", json={"title": "Outage", "description": "grid down"})
    client.post("/api/thresholds", json={"name": "Grid", "sector": "power",
                                         "below_pct": 40, "severity": "critical"})
    client.post("/api/log", json={"action": "incident declared"})
    return a, b


class TestSaveAndList:
    def test_save_reports_the_stored_name(self, client, populated):
        r = client.post("/api/scenarios/save", json={"name": "Exercise One"})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "name": "Exercise One"}

    def test_saved_scenario_shows_up_in_the_listing(self, client, populated):
        client.post("/api/scenarios/save", json={"name": "Exercise One"})
        assert client.get("/api/scenarios").json() == ["Exercise One"]

    def test_listing_is_sorted(self, client):
        for name in ("Charlie", "alpha", "Bravo"):
            client.post("/api/scenarios/save", json={"name": name})
        assert client.get("/api/scenarios").json() == sorted(["Charlie", "alpha", "Bravo"])

    def test_writes_into_the_scenarios_directory(self, client, clean_state, populated):
        client.post("/api/scenarios/save", json={"name": "On Disk"})
        written = list(clean_state.glob("*.json"))
        assert [f.name for f in written] == ["On Disk.json"]
        assert json.loads(written[0].read_text())["name"] == "On Disk"

    def test_saving_the_same_name_overwrites(self, client, make_pin):
        make_pin(name="first")
        client.post("/api/scenarios/save", json={"name": "Reused"})
        client.delete("/api/pins")
        make_pin(name="second")
        make_pin(name="third")
        client.post("/api/scenarios/save", json={"name": "Reused"})

        assert client.get("/api/scenarios").json() == ["Reused"]
        client.post("/api/scenarios/load", json={"name": "Reused"})
        assert len(client.get("/api/pins").json()) == 2


class TestLoad:
    def test_restores_every_store(self, client, populated):
        client.post("/api/scenarios/save", json={"name": "Full"})
        client.post("/api/state/clear")

        r = client.post("/api/scenarios/load", json={"name": "Full"})
        assert r.status_code == 200
        assert r.json()["count"] == 2

        assert len(client.get("/api/pins").json()) == 2
        assert len(client.get("/api/edges").json()) == 1
        assert len(client.get("/api/injects").json()) == 1
        assert len(client.get("/api/thresholds").json()) == 1
        assert len(client.get("/api/log").json()) == 1

    def test_replaces_rather_than_merges(self, client, make_pin):
        make_pin(name="saved")
        client.post("/api/scenarios/save", json={"name": "Snapshot"})

        client.delete("/api/pins")
        make_pin(name="added later")

        client.post("/api/scenarios/load", json={"name": "Snapshot"})
        names = [p["name"] for p in client.get("/api/pins").json().values()]
        assert names == ["saved"]

    def test_preserves_pin_detail(self, client, populated):
        client.post("/api/scenarios/save", json={"name": "Detail"})
        client.post("/api/state/clear")
        client.post("/api/scenarios/load", json={"name": "Detail"})

        pins = client.get("/api/pins").json()
        sub = next(p for p in pins.values() if p["name"] == "Substation")
        assert sub["status"] == "Compromised"
        assert sub["category"] == "Power Plants"
        assert sub["status_history"][0]["status"] == "Compromised"

    def test_unknown_scenario_is_404(self, client):
        assert client.post("/api/scenarios/load",
                           json={"name": "never saved"}).status_code == 404


class TestDelete:
    def test_removes_it_from_the_listing(self, client):
        client.post("/api/scenarios/save", json={"name": "Temp"})
        assert client.delete("/api/scenarios/Temp").status_code == 200
        assert client.get("/api/scenarios").json() == []

    def test_unknown_scenario_is_404(self, client):
        assert client.delete("/api/scenarios/nothing-here").status_code == 404

    def test_deleting_does_not_touch_loaded_state(self, client, make_pin):
        make_pin(name="still here")
        client.post("/api/scenarios/save", json={"name": "Temp"})
        client.delete("/api/scenarios/Temp")
        assert len(client.get("/api/pins").json()) == 1


class TestNameSanitising:
    @pytest.mark.parametrize("raw,stored", [
        ("Exercise One", "Exercise One"),
        ("with-hyphens_and_underscores", "with-hyphens_and_underscores"),
        ("drop/slashes", "dropslashes"),
        ("dots...everywhere", "dotseverywhere"),
        ("  padded  ", "padded"),
        ("emoji \U0001F600 stripped", "emoji  stripped"),
    ])
    def test_name_is_reduced_to_safe_characters(self, client, raw, stored):
        r = client.post("/api/scenarios/save", json={"name": raw})
        assert r.status_code == 200
        assert r.json()["name"] == stored

    def test_name_that_sanitises_to_nothing_is_rejected(self, client):
        r = client.post("/api/scenarios/save", json={"name": "..."})
        assert r.status_code == 400

    def test_overlong_name_is_rejected_by_the_model(self, client):
        assert client.post("/api/scenarios/save",
                           json={"name": "x" * 65}).status_code == 422


class TestPathTraversal:
    """Scenario names reach the filesystem, so they must not be able to escape."""

    @pytest.mark.parametrize("attack", [
        "../../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "/etc/passwd",
        "....//....//etc/passwd",
        "..\\..\\windows\\system32",
    ])
    def test_traversal_attempts_cannot_escape_the_directory(
            self, client, clean_state, attack):
        client.post("/api/scenarios/save", json={"name": attack})

        # Whatever it saved as, it landed inside SCENARIOS_DIR and nowhere else.
        for written in clean_state.rglob("*"):
            assert written.parent == clean_state
        assert not (clean_state.parent / "etc").exists()

    def test_traversal_load_does_not_read_outside(self, client, clean_state):
        outside = clean_state.parent / "secret.json"
        outside.write_text(json.dumps({"pins": {"x": {"name": "leaked"}}}))

        r = client.post("/api/scenarios/load", json={"name": "../secret"})
        assert r.status_code == 404
        assert client.get("/api/pins").json() == {}


class TestStateClear:
    def test_empties_every_store(self, client, populated):
        r = client.post("/api/state/clear")
        assert r.json() == {"ok": True}
        assert client.get("/api/pins").json() == {}
        assert client.get("/api/edges").json() == []
        assert client.get("/api/injects").json() == []
        assert client.get("/api/thresholds").json() == []
        assert client.get("/api/log").json() == []

    def test_leaves_saved_scenarios_on_disk(self, client, populated):
        client.post("/api/scenarios/save", json={"name": "Survives"})
        client.post("/api/state/clear")
        assert client.get("/api/scenarios").json() == ["Survives"]
