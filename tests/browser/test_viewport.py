"""Where the map points.

Loading a scenario used to leave the view on the default US-wide frame while
every asset sat unseen somewhere else, and filtering dimmed the misses without
ever going to the hit.
"""


def _center(page):
    return page.evaluate(
        "async () => { const c = (await import('/js/map.js')).getMap().getCenter();"
        " return [c.lat, c.lng]; }")


def _zoom(page):
    return page.evaluate(
        "async () => (await import('/js/map.js')).getMap().getZoom()")


def test_first_load_frames_the_assets(seeded, app_page):
    """The default view is [39.5, -98.35] at z5 -- the whole country."""
    page = app_page
    page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length >= 5")
    page.wait_for_timeout(500)

    lat, lon = _center(page)
    # The seeded pins run from 38.90/-77.03 to 38.94/-77.07.
    assert 38.8 < lat < 39.0, f"centred on {lat}, not the assets"
    assert -77.2 < lon < -76.9, f"centred on {lon}, not the assets"
    assert _zoom(page) > 5, "still at the default country-wide zoom"


def test_enter_in_the_filter_goes_to_the_match(seeded, right_panel):
    page = right_panel
    page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length >= 5")

    page.evaluate("async () => (await import('/js/map.js')).getMap().setView([39.5, -98.35], 5)")
    page.wait_for_timeout(200)
    assert _zoom(page) == 5

    page.fill("#pin-filter-inp", "Industrial Bank")
    page.press("#pin-filter-inp", "Enter")
    page.wait_for_timeout(600)

    lat, lon = _center(page)
    assert 38.8 < lat < 39.0 and -77.2 < lon < -76.9, f"did not travel to the match: {lat},{lon}"
    assert _zoom(page) > 5

    page.fill("#pin-filter-inp", "")
