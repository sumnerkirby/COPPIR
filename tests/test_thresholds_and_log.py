"""Alert thresholds and the decision log."""
import pytest


class TestThresholds:
    def test_create_returns_it_with_an_id(self, client):
        r = client.post("/api/thresholds", json={
            "name": "Grid integrity", "sector": "power",
            "below_pct": 40, "severity": "critical"})
        assert r.status_code == 201
        t = r.json()
        assert t["id"] and t["name"] == "Grid integrity" and t["below_pct"] == 40

    def test_defaults(self, client):
        t = client.post("/api/thresholds",
                        json={"name": "Watch", "sector": "medical"}).json()
        assert t["below_pct"] == 50
        assert t["severity"] == "warning"

    @pytest.mark.parametrize("sector", [
        "all", "medical", "government", "power", "emergency", "civilian", "financial"])
    def test_accepts_every_known_sector(self, client, sector):
        r = client.post("/api/thresholds", json={"name": "s", "sector": sector})
        assert r.status_code == 201

    def test_rejects_unknown_sector(self, client):
        r = client.post("/api/thresholds", json={"name": "s", "sector": "logistics"})
        assert r.status_code == 422

    @pytest.mark.parametrize("pct", [-1, 101])
    def test_rejects_out_of_range_percentage(self, client, pct):
        r = client.post("/api/thresholds",
                        json={"name": "s", "sector": "power", "below_pct": pct})
        assert r.status_code == 422

    @pytest.mark.parametrize("pct", [0, 100])
    def test_accepts_boundary_percentages(self, client, pct):
        r = client.post("/api/thresholds",
                        json={"name": "s", "sector": "power", "below_pct": pct})
        assert r.status_code == 201

    def test_several_thresholds_can_watch_one_sector(self, client):
        for pct in (60, 40, 20):
            client.post("/api/thresholds",
                        json={"name": f"power {pct}", "sector": "power", "below_pct": pct})
        assert len(client.get("/api/thresholds").json()) == 3

    def test_delete_removes_only_the_named_one(self, client):
        a = client.post("/api/thresholds", json={"name": "a", "sector": "power"}).json()
        b = client.post("/api/thresholds", json={"name": "b", "sector": "medical"}).json()
        assert client.delete(f"/api/thresholds/{a['id']}").status_code == 200
        assert [t["id"] for t in client.get("/api/thresholds").json()] == [b["id"]]

    def test_unknown_threshold_is_404(self, client):
        assert client.delete("/api/thresholds/nope").status_code == 404


class TestDecisionLog:
    def test_manual_entry_is_marked_not_automatic(self, client):
        r = client.post("/api/log", json={"action": "incident declared"})
        assert r.status_code == 201
        entry = r.json()
        assert entry["auto"] is False
        assert entry["id"] and entry["timestamp"]

    def test_entries_keep_insertion_order(self, client):
        for n in ("first", "second", "third"):
            client.post("/api/log", json={"action": n})
        assert [e["action"] for e in client.get("/api/log").json()] == [
            "first", "second", "third"]

    def test_entry_can_reference_an_asset(self, client, make_pin):
        pin = make_pin(name="Rosslyn Substation")
        entry = client.post("/api/log", json={
            "action": "IR team dispatched",
            "asset_name": pin["name"], "asset_pid": pin["id"]}).json()
        assert entry["asset_name"] == "Rosslyn Substation"
        assert entry["asset_pid"] == pin["id"]

    def test_rejects_empty_action(self, client):
        assert client.post("/api/log", json={"action": ""}).status_code == 422

    def test_rejects_overlong_action(self, client):
        assert client.post("/api/log", json={"action": "x" * 501}).status_code == 422

    def test_starts_empty(self, client):
        assert client.get("/api/log").json() == []
