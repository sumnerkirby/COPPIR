"""Real-time sync.

Every state change is meant to reach every connected client, and a client
joining mid-exercise is meant to be handed the whole picture immediately.
Those two properties are what the interface relies on, so they are worth
holding in place.
"""
import pytest


@pytest.fixture
def ws(client):
    """A connected client with the opening full_state already consumed."""
    with client.websocket_connect("/ws") as socket:
        opening = socket.receive_json()
        assert opening["type"] == "full_state"
        yield socket


class TestConnect:
    def test_sends_full_state_immediately(self, client):
        with client.websocket_connect("/ws") as socket:
            msg = socket.receive_json()
        assert msg["type"] == "full_state"
        assert set(msg) == {"type", "pins", "injects", "edges", "thresholds", "log"}

    def test_full_state_carries_existing_session(self, client, make_pin):
        a = make_pin(name="Substation")
        b = make_pin(name="Hospital")
        client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        client.post("/api/injects", json={"title": "t", "description": "d"})
        client.post("/api/log", json={"action": "declared"})

        with client.websocket_connect("/ws") as socket:
            msg = socket.receive_json()

        assert set(msg["pins"]) == {a["id"], b["id"]}
        assert len(msg["edges"]) == 1
        assert len(msg["injects"]) == 1
        assert len(msg["log"]) == 1

    def test_a_late_joiner_gets_the_same_picture(self, client, make_pin):
        """Someone opening a second window mid-exercise is not left behind."""
        make_pin(name="placed before they connected")
        with client.websocket_connect("/ws") as socket:
            assert len(socket.receive_json()["pins"]) == 1


class TestPinBroadcasts:
    def test_create(self, client, ws):
        client.post("/api/pins", json={"name": "New", "lat": 1.0, "lon": 1.0})
        msg = ws.receive_json()
        assert msg["type"] == "pin_add"
        assert msg["pin"]["name"] == "New"

    def test_update(self, client, make_pin, ws):
        pin = make_pin()
        ws.receive_json()                       # the create
        client.put(f"/api/pins/{pin['id']}", json={"status": "Contained"})
        msg = ws.receive_json()
        assert msg["type"] == "pin_update"
        assert msg["pin"]["status"] == "Contained"

    def test_delete_carries_the_id(self, client, make_pin, ws):
        pin = make_pin()
        ws.receive_json()
        client.delete(f"/api/pins/{pin['id']}")
        msg = ws.receive_json()
        assert msg["type"] == "pin_delete"
        assert msg["pid"] == pin["id"]

    def test_bulk_create_is_one_message(self, client, ws):
        client.post("/api/pins/bulk", json={"items": [
            {"name": "A", "lat": 1.0, "lon": 1.0},
            {"name": "B", "lat": 2.0, "lon": 2.0},
        ]})
        msg = ws.receive_json()
        assert msg["type"] == "bulk_add"
        assert len(msg["pins"]) == 2

    def test_bulk_status_is_one_message(self, client, make_pin, ws):
        make_pin(category="Banks")
        make_pin(category="Banks")
        ws.receive_json(); ws.receive_json()
        client.post("/api/pins/bulk-status",
                    json={"category": "Banks", "status": "Compromised"})
        msg = ws.receive_json()
        assert msg["type"] == "bulk_update"
        assert {p["status"] for p in msg["pins"]} == {"Compromised"}

    def test_clear_all(self, client, make_pin, ws):
        pin = make_pin()
        ws.receive_json()
        client.delete("/api/pins")
        msg = ws.receive_json()
        assert msg["type"] == "pins_cleared"
        assert msg["pids"] == [pin["id"]]


class TestEdgeBroadcasts:
    def test_create_and_delete(self, client, make_pin, ws):
        a, b = make_pin(name="a"), make_pin(name="b")
        ws.receive_json(); ws.receive_json()

        edge = client.post("/api/edges",
                           json={"from_pid": a["id"], "to_pid": b["id"]}).json()
        assert ws.receive_json()["type"] == "edge_add"

        client.delete(f"/api/edges/{edge['id']}")
        msg = ws.receive_json()
        assert msg["type"] == "edge_delete"
        assert msg["eid"] == edge["id"]


class TestInjectBroadcasts:
    def test_queued_and_deleted(self, client, ws):
        inj = client.post("/api/injects",
                          json={"title": "t", "description": "d"}).json()
        assert ws.receive_json()["type"] == "inject_queued"

        client.delete(f"/api/injects/{inj['id']}")
        msg = ws.receive_json()
        assert msg["type"] == "inject_delete"
        assert msg["iid"] == inj["id"]

    def test_triggered_carries_pins_and_the_log_entry(self, client, make_pin, ws):
        """One message has to be enough to resync a client fully."""
        pin = make_pin(status="Clean")
        ws.receive_json()
        inj = client.post("/api/injects", json={
            "title": "Outage", "description": "grid down",
            "target_pid": pin["id"], "target_status": "Compromised"}).json()
        ws.receive_json()

        client.post(f"/api/injects/{inj['id']}/trigger")
        msg = ws.receive_json()
        assert msg["type"] == "inject_triggered"
        assert msg["pins"][pin["id"]]["status"] == "Compromised"
        assert msg["log_entry"]["auto"] is True
        assert msg["inject"]["triggered_at"] is not None


class TestLogBroadcast:
    def test_manual_entry(self, client, ws):
        client.post("/api/log", json={"action": "declared"})
        msg = ws.receive_json()
        assert msg["type"] == "log_entry"
        assert msg["entry"]["action"] == "declared"


class TestFullStateResends:
    def test_scenario_load_resyncs_everyone(self, client, make_pin, ws):
        make_pin(name="saved")
        ws.receive_json()
        client.post("/api/scenarios/save", json={"name": "Snap"})
        client.post("/api/state/clear")
        assert ws.receive_json()["type"] == "full_state"

        client.post("/api/scenarios/load", json={"name": "Snap"})
        msg = ws.receive_json()
        assert msg["type"] == "full_state"
        assert [p["name"] for p in msg["pins"].values()] == ["saved"]

    def test_state_clear_sends_an_empty_picture(self, client, make_pin, ws):
        make_pin()
        ws.receive_json()
        client.post("/api/state/clear")
        msg = ws.receive_json()
        assert msg["type"] == "full_state"
        assert msg["pins"] == {} and msg["log"] == []


class TestMultipleClients:
    def test_both_windows_see_the_same_change(self, client):
        """Two windows on one machine is the normal way this gets used."""
        with client.websocket_connect("/ws") as one, \
             client.websocket_connect("/ws") as two:
            one.receive_json()
            two.receive_json()

            client.post("/api/pins", json={"name": "Shared", "lat": 1.0, "lon": 1.0})

            for socket in (one, two):
                msg = socket.receive_json()
                assert msg["type"] == "pin_add"
                assert msg["pin"]["name"] == "Shared"
