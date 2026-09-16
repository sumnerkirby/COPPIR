"""Pin CRUD, validation, and status history."""
import pytest


class TestCreate:
    def test_returns_201_with_generated_fields(self, client):
        r = client.post("/api/pins", json={
            "name": "Rosslyn Substation", "category": "Power Plants",
            "lat": 38.8968, "lon": -77.0719,
        })
        assert r.status_code == 201
        pin = r.json()
        assert pin["id"]
        assert pin["pinned_at"]
        assert pin["name"] == "Rosslyn Substation"

    def test_defaults_to_clean_and_healthy(self, make_pin):
        pin = make_pin()
        assert pin["status"] == "Clean"
        assert pin["op_status"] == "Healthy"

    def test_seeds_status_history_with_initial_status(self, make_pin):
        pin = make_pin(status="Compromised")
        assert [h["status"] for h in pin["status_history"]] == ["Compromised"]
        assert pin["status_history"][0]["timestamp"]

    def test_appears_in_collection_keyed_by_id(self, client, make_pin):
        pin = make_pin()
        all_pins = client.get("/api/pins").json()
        assert list(all_pins) == [pin["id"]]


class TestCreateValidation:
    @pytest.mark.parametrize("field,value", [
        ("status", "Melted"),
        ("op_status", "Vibing"),
        ("pin_color", "red"),          # must be #RRGGBB
        ("pin_color", "#ff0"),         # shorthand hex not accepted
        ("lat", 91),
        ("lat", -91),
        ("lon", 181),
        ("lon", -181),
        ("name", ""),                  # min_length=1
    ])
    def test_rejects_bad_field(self, client, field, value):
        body = {"name": "x", "lat": 0.0, "lon": 0.0}
        body[field] = value
        assert client.post("/api/pins", json=body).status_code == 422

    def test_rejects_overlong_name(self, client):
        r = client.post("/api/pins", json={"name": "x" * 201, "lat": 0.0, "lon": 0.0})
        assert r.status_code == 422

    def test_accepts_boundary_coordinates(self, client):
        for lat, lon in [(90, 180), (-90, -180), (0, 0)]:
            r = client.post("/api/pins", json={"name": "edge", "lat": lat, "lon": lon})
            assert r.status_code == 201, f"{lat},{lon} should be valid"


class TestUpdate:
    def test_partial_update_leaves_other_fields_alone(self, client, make_pin):
        pin = make_pin(name="Original", notes="keep me")
        r = client.put(f"/api/pins/{pin['id']}", json={"status": "Contained"})
        assert r.status_code == 200
        updated = r.json()
        assert updated["status"] == "Contained"
        assert updated["name"] == "Original"
        assert updated["notes"] == "keep me"

    def test_status_change_appends_history(self, client, make_pin):
        pin = make_pin(status="Clean")
        client.put(f"/api/pins/{pin['id']}", json={"status": "Monitored"})
        r = client.put(f"/api/pins/{pin['id']}", json={"status": "Compromised"})
        assert [h["status"] for h in r.json()["status_history"]] == [
            "Clean", "Monitored", "Compromised"]

    def test_rewriting_same_status_does_not_append(self, client, make_pin):
        """The history is a record of changes, not of writes."""
        pin = make_pin(status="Monitored")
        for _ in range(3):
            r = client.put(f"/api/pins/{pin['id']}", json={"status": "Monitored"})
        assert len(r.json()["status_history"]) == 1

    def test_op_status_change_is_not_recorded_in_history(self, client, make_pin):
        """status_history tracks security status only."""
        pin = make_pin()
        r = client.put(f"/api/pins/{pin['id']}", json={"op_status": "Critical"})
        assert r.json()["op_status"] == "Critical"
        assert len(r.json()["status_history"]) == 1

    def test_unknown_pin_is_404(self, client):
        assert client.put("/api/pins/nope", json={"status": "Clean"}).status_code == 404

    def test_rejects_bad_status(self, client, make_pin):
        pin = make_pin()
        r = client.put(f"/api/pins/{pin['id']}", json={"status": "Toast"})
        assert r.status_code == 422


class TestDelete:
    def test_removes_the_pin(self, client, make_pin):
        pin = make_pin()
        assert client.delete(f"/api/pins/{pin['id']}").status_code == 200
        assert client.get("/api/pins").json() == {}

    def test_deleting_twice_is_404(self, client, make_pin):
        pin = make_pin()
        client.delete(f"/api/pins/{pin['id']}")
        assert client.delete(f"/api/pins/{pin['id']}").status_code == 404

    def test_clear_all_reports_count(self, client, make_pin):
        for i in range(3):
            make_pin(name=f"pin {i}")
        r = client.delete("/api/pins")
        assert r.json() == {"ok": True, "count": 3}
        assert client.get("/api/pins").json() == {}


class TestBulkCreate:
    def test_applies_shared_status_to_every_item(self, client):
        r = client.post("/api/pins/bulk", json={
            "items": [
                {"name": "A", "category": "Hospitals", "lat": 1.0, "lon": 1.0},
                {"name": "B", "category": "Hospitals", "lat": 2.0, "lon": 2.0},
            ],
            "status": "Monitored", "op_status": "Degraded",
        })
        assert r.status_code == 201
        created = r.json()
        assert len(created) == 2
        assert {p["status"] for p in created} == {"Monitored"}
        assert {p["op_status"] for p in created} == {"Degraded"}

    def test_empty_item_list_creates_nothing(self, client):
        r = client.post("/api/pins/bulk", json={"items": []})
        assert r.status_code == 201
        assert r.json() == []
        assert client.get("/api/pins").json() == {}


class TestBulkStatus:
    def test_only_touches_the_named_category(self, client, make_pin):
        hospital = make_pin(name="H", category="Hospitals")
        bank = make_pin(name="B", category="Banks")

        r = client.post("/api/pins/bulk-status",
                        json={"category": "Hospitals", "status": "Compromised"})
        assert r.json()["count"] == 1

        pins = client.get("/api/pins").json()
        assert pins[hospital["id"]]["status"] == "Compromised"
        assert pins[bank["id"]]["status"] == "Clean"

    def test_omitting_category_applies_to_everything(self, client, make_pin):
        make_pin(name="H", category="Hospitals")
        make_pin(name="B", category="Banks")
        r = client.post("/api/pins/bulk-status", json={"status": "Contained"})
        assert r.json()["count"] == 2
        assert {p["status"] for p in client.get("/api/pins").json().values()} == {"Contained"}

    def test_records_the_change_in_history(self, client, make_pin):
        pin = make_pin(status="Clean", category="Banks")
        client.post("/api/pins/bulk-status", json={"category": "Banks", "status": "Compromised"})
        history = client.get("/api/pins").json()[pin["id"]]["status_history"]
        assert [h["status"] for h in history] == ["Clean", "Compromised"]
