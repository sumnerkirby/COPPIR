"""Injects: pre-authored events an exercise controller fires during a run."""
import pytest


@pytest.fixture
def inject(client):
    def _make(**overrides):
        body = {"title": "Substation outage", "description": "grid down"}
        body.update(overrides)
        r = client.post("/api/injects", json=body)
        assert r.status_code == 201, r.text
        return r.json()
    return _make


class TestCreate:
    def test_starts_untriggered(self, inject):
        i = inject()
        assert i["id"]
        assert i["created_at"]
        assert i["triggered_at"] is None

    def test_defaults_to_warning_severity(self, inject):
        assert inject()["severity"] == "warning"

    @pytest.mark.parametrize("severity", ["info", "warning", "critical"])
    def test_accepts_each_severity(self, inject, severity):
        assert inject(severity=severity)["severity"] == severity

    def test_rejects_unknown_severity(self, client):
        r = client.post("/api/injects", json={"title": "x", "description": "y",
                                              "severity": "catastrophic"})
        assert r.status_code == 422

    def test_rejects_unknown_target_status(self, client):
        r = client.post("/api/injects", json={"title": "x", "description": "y",
                                              "target_status": "Melted"})
        assert r.status_code == 422

    def test_rejects_malformed_new_pin(self, client):
        r = client.post("/api/injects", json={
            "title": "x", "description": "y",
            "new_pin": {"name": "spawn", "lat": 999, "lon": 0},
        })
        assert r.status_code == 422

    def test_shows_up_in_the_listing(self, client, inject):
        i = inject()
        assert [x["id"] for x in client.get("/api/injects").json()] == [i["id"]]


class TestDelete:
    def test_removes_it(self, client, inject):
        i = inject()
        assert client.delete(f"/api/injects/{i['id']}").status_code == 200
        assert client.get("/api/injects").json() == []

    def test_unknown_inject_is_404(self, client):
        assert client.delete("/api/injects/nope").status_code == 404


class TestTrigger:
    def test_stamps_triggered_at(self, client, inject):
        i = inject()
        r = client.post(f"/api/injects/{i['id']}/trigger")
        assert r.status_code == 200
        assert r.json()["triggered_at"] is not None

    def test_moves_the_target_pin_to_the_new_status(self, client, make_pin, inject):
        pin = make_pin(status="Clean")
        i = inject(target_pid=pin["id"], target_status="Compromised")
        client.post(f"/api/injects/{i['id']}/trigger")

        updated = client.get("/api/pins").json()[pin["id"]]
        assert updated["status"] == "Compromised"
        assert [h["status"] for h in updated["status_history"]] == ["Clean", "Compromised"]

    def test_spawns_the_new_pin(self, client, inject):
        i = inject(new_pin={"name": "Relocated CP", "category": "Asset",
                            "lat": 38.9, "lon": -77.0})
        client.post(f"/api/injects/{i['id']}/trigger")

        pins = list(client.get("/api/pins").json().values())
        assert [p["name"] for p in pins] == ["Relocated CP"]
        assert pins[0]["status"] == "Under Investigation"   # the documented default

    def test_writes_an_automatic_log_entry(self, client, inject):
        i = inject(title="Substation outage", description="grid down")
        client.post(f"/api/injects/{i['id']}/trigger")

        log = client.get("/api/log").json()
        assert len(log) == 1
        assert log[0]["auto"] is True
        assert "Substation outage" in log[0]["action"]
        assert log[0]["notes"] == "grid down"

    def test_log_entry_names_the_target_pin(self, client, make_pin, inject):
        pin = make_pin(name="Rosslyn Substation")
        i = inject(target_pid=pin["id"], target_status="Compromised")
        client.post(f"/api/injects/{i['id']}/trigger")

        entry = client.get("/api/log").json()[0]
        assert entry["asset_name"] == "Rosslyn Substation"
        assert entry["asset_pid"] == pin["id"]

    def test_does_everything_at_once(self, client, make_pin, inject):
        """Status change, new pin and log entry land together."""
        pin = make_pin(status="Clean")
        i = inject(target_pid=pin["id"], target_status="Contained",
                   new_pin={"name": "Spawned", "lat": 1.0, "lon": 1.0})
        client.post(f"/api/injects/{i['id']}/trigger")

        pins = client.get("/api/pins").json()
        assert len(pins) == 2
        assert pins[pin["id"]]["status"] == "Contained"
        assert len(client.get("/api/log").json()) == 1

    def test_unknown_inject_is_404(self, client):
        assert client.post("/api/injects/nope/trigger").status_code == 404

    def test_missing_target_pin_is_tolerated(self, client, inject):
        """A target deleted before the inject fires must not blow up the trigger."""
        i = inject(target_pid="deleted-pin", target_status="Compromised")
        assert client.post(f"/api/injects/{i['id']}/trigger").status_code == 200
