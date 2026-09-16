"""Edges: the connections drawn between two pins."""
import pytest


@pytest.fixture
def two_pins(make_pin):
    return make_pin(name="Substation"), make_pin(name="Hospital")


class TestCreate:
    def test_links_two_existing_pins(self, client, two_pins):
        a, b = two_pins
        r = client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        assert r.status_code == 201
        edge = r.json()
        assert edge["id"]
        assert edge["from_pid"] == a["id"]
        assert edge["to_pid"] == b["id"]

    def test_defaults_edge_type_and_label(self, client, two_pins):
        a, b = two_pins
        edge = client.post("/api/edges",
                           json={"from_pid": a["id"], "to_pid": b["id"]}).json()
        assert edge["edge_type"] == "connection"
        assert edge["label"] == ""

    def test_keeps_the_label_it_was_given(self, client, two_pins):
        a, b = two_pins
        edge = client.post("/api/edges", json={
            "from_pid": a["id"], "to_pid": b["id"],
            "label": "primary feed", "edge_type": "dependency",
        }).json()
        assert edge["label"] == "primary feed"
        assert edge["edge_type"] == "dependency"

    @pytest.mark.parametrize("missing", ["from_pid", "to_pid"])
    def test_rejects_an_endpoint_that_does_not_exist(self, client, two_pins, missing):
        a, b = two_pins
        body = {"from_pid": a["id"], "to_pid": b["id"]}
        body[missing] = "not-a-real-pin"
        r = client.post("/api/edges", json=body)
        assert r.status_code == 400
        assert client.get("/api/edges").json() == []

    def test_rejects_overlong_label(self, client, two_pins):
        a, b = two_pins
        r = client.post("/api/edges", json={
            "from_pid": a["id"], "to_pid": b["id"], "label": "x" * 201})
        assert r.status_code == 422


class TestList:
    def test_starts_empty(self, client):
        assert client.get("/api/edges").json() == []

    def test_returns_every_edge(self, client, make_pin):
        a, b, c = (make_pin(name=n) for n in "abc")
        client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        client.post("/api/edges", json={"from_pid": b["id"], "to_pid": c["id"]})
        assert len(client.get("/api/edges").json()) == 2


class TestDelete:
    def test_removes_the_edge(self, client, two_pins):
        a, b = two_pins
        edge = client.post("/api/edges",
                           json={"from_pid": a["id"], "to_pid": b["id"]}).json()
        assert client.delete(f"/api/edges/{edge['id']}").status_code == 200
        assert client.get("/api/edges").json() == []

    def test_deleting_twice_is_404(self, client, two_pins):
        a, b = two_pins
        edge = client.post("/api/edges",
                           json={"from_pid": a["id"], "to_pid": b["id"]}).json()
        client.delete(f"/api/edges/{edge['id']}")
        assert client.delete(f"/api/edges/{edge['id']}").status_code == 404

    def test_removing_an_edge_leaves_its_pins_alone(self, client, two_pins):
        a, b = two_pins
        edge = client.post("/api/edges",
                           json={"from_pid": a["id"], "to_pid": b["id"]}).json()
        client.delete(f"/api/edges/{edge['id']}")
        assert set(client.get("/api/pins").json()) == {a["id"], b["id"]}


class TestClearAllPins:
    def test_wipes_edges_too(self, client, two_pins):
        """Edges cannot outlive the pins they join, so clearing pins clears them."""
        a, b = two_pins
        client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        client.delete("/api/pins")
        assert client.get("/api/edges").json() == []


class TestPinDeleteCascade:
    """Deleting a pin has to take its edges with it.

    The server used to leave them behind. Nothing visibly broke, because the
    frontend drops dangling edges on its own and renderEdge bails when an
    endpoint is missing -- but they survived in every subsequent full_state
    and were written into saved scenarios.
    """

    def test_deleting_a_pin_removes_edges_touching_it(self, client, two_pins):
        a, b = two_pins
        client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        client.delete(f"/api/pins/{a['id']}")
        assert client.get("/api/edges").json() == []

    def test_works_from_either_end(self, client, two_pins):
        a, b = two_pins
        client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        client.delete(f"/api/pins/{b['id']}")
        assert client.get("/api/edges").json() == []

    def test_removes_every_edge_touching_that_pin(self, client, make_pin):
        hub = make_pin(name="Substation")
        spokes = [make_pin(name=f"load {i}") for i in range(3)]
        for s in spokes:
            client.post("/api/edges", json={"from_pid": hub["id"], "to_pid": s["id"]})
        assert len(client.get("/api/edges").json()) == 3

        client.delete(f"/api/pins/{hub['id']}")
        assert client.get("/api/edges").json() == []

    def test_leaves_unrelated_edges_alone(self, client, make_pin):
        a, b, c, d = (make_pin(name=n) for n in "abcd")
        doomed = client.post("/api/edges",
                             json={"from_pid": a["id"], "to_pid": b["id"]}).json()
        survivor = client.post("/api/edges",
                               json={"from_pid": c["id"], "to_pid": d["id"]}).json()

        client.delete(f"/api/pins/{a['id']}")
        remaining = client.get("/api/edges").json()
        assert [e["id"] for e in remaining] == [survivor["id"]]
        assert doomed["id"] not in [e["id"] for e in remaining]

    def test_orphans_do_not_reach_a_saved_scenario(self, client, two_pins):
        """The path that made this worth fixing: orphans were persisted."""
        a, b = two_pins
        client.post("/api/edges", json={"from_pid": a["id"], "to_pid": b["id"]})
        client.delete(f"/api/pins/{a['id']}")

        client.post("/api/scenarios/save", json={"name": "after delete"})
        client.post("/api/state/clear")
        client.post("/api/scenarios/load", json={"name": "after delete"})

        assert client.get("/api/edges").json() == []
        assert list(client.get("/api/pins").json()) == [b["id"]]
