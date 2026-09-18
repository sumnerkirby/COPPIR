"""Websocket sync: the thing the whole interface is built on.

The API tests cover what the server broadcasts. These cover whether an open
page actually acts on it, which is a different question and the one that
matters during an exercise.
"""


def test_seeded_state_is_rendered_on_load(seeded, app_page):
    app_page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length === 5")
    assert app_page.locator(".leaflet-marker-icon").count() == 5


def test_a_pin_created_elsewhere_appears_without_reload(seeded, app_page, api):
    """Two windows on one machine is the normal way this gets used."""
    before = app_page.locator(".leaflet-marker-icon").count()

    api.post("/api/pins", json={
        "name": "Late Arrival", "category": "Fire Stations",
        "lat": 38.95, "lon": -77.05,
    }).raise_for_status()

    app_page.wait_for_function(
        f"() => document.querySelectorAll('.leaflet-marker-icon').length === {before + 1}")


def test_a_status_change_elsewhere_updates_the_sitrep(seeded, app_page, api):
    app_page.wait_for_function("() => document.getElementById('cnt-comp').textContent === '2'")

    api.put(f"/api/pins/{seeded['Industrial Bank']}",
            json={"status": "Compromised"}).raise_for_status()

    app_page.wait_for_function("() => document.getElementById('cnt-comp').textContent === '3'")


def test_a_deletion_elsewhere_removes_the_marker(seeded, app_page, api):
    app_page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length === 5")

    api.delete(f"/api/pins/{seeded['GW Hospital']}").raise_for_status()

    app_page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length === 4")


def test_deleting_a_pin_also_drops_its_edge(seeded, app_page, api):
    """The orphaned-edge fix, seen from the browser."""
    app_page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-overlay-pane path').length >= 1")

    api.delete(f"/api/pins/{seeded['Rosslyn Substation']}").raise_for_status()

    app_page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-overlay-pane path').length === 0")
    assert api.get("/api/edges").json() == []


def test_a_log_entry_elsewhere_appears_in_the_panel(app_page, api):
    api.post("/api/log", json={"action": "incident declared"}).raise_for_status()
    app_page.wait_for_function(
        "() => document.querySelectorAll('.log-entry').length === 1")
    assert "incident declared" in app_page.inner_text(".log-entry")
