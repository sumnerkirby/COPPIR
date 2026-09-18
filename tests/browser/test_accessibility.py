"""Status has to survive being read without colour, and the key has to agree
with the map it describes."""

SECURITY = ["Compromised", "Under Investigation", "Contained", "Monitored", "Clean"]
OPERATIONAL = ["Healthy", "Degraded", "Critical", "Offline"]


def test_markers_carry_a_cue_that_is_not_colour(app_page, seeded):
    """Compromised, Contained and Under Investigation are red, orange and
    amber -- colour alone does not separate them."""
    page = app_page
    page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length >= 5")

    glyphs = page.evaluate(
        "() => [...document.querySelectorAll('.pin-status-glyph')].map(g => g.textContent)")
    assert len(glyphs) >= 5, "every marker should carry a status glyph"

    # The seeded set is two Compromised, two Clean, one Monitored.
    assert glyphs.count("✕") == 2
    assert glyphs.count("✓") == 2
    assert glyphs.count("◦") == 1

    # Operational status varies the ring style, not just its colour.
    styles = page.evaluate("""() => [...document.querySelectorAll('.pin-icon')]
        .map(p => p.style.borderStyle)""")
    assert len(set(styles)) > 1, f"every ring drew the same style: {set(styles)}"


def test_legend_covers_every_status(app_page):
    page = app_page
    page.wait_for_selector("#map-legend")
    text = page.text_content("#legend-body")
    for status in SECURITY + OPERATIONAL:
        assert status in text, f"{status} missing from the key"


def test_legend_hides_and_the_choice_sticks(app_page):
    page = app_page
    assert page.locator("#map-legend").is_visible()

    page.click("#legend-btn")
    page.wait_for_selector("#map-legend", state="hidden")
    assert page.get_attribute("#legend-btn", "aria-expanded") == "false"

    page.reload(wait_until="networkidle")
    page.wait_for_function("() => document.getElementById('legend-btn')")
    assert page.locator("#map-legend").is_hidden(), "the choice did not persist"

    page.click("#legend-btn")
    page.wait_for_selector("#map-legend", state="visible")


def test_legend_keeps_clear_of_the_panels(app_page):
    """The left panel can grow to the full height of the window, and the log
    and tools panels both slide over where the key sits."""
    page = app_page
    overlaps = page.evaluate("""() => {
        const box = id => document.getElementById(id).getBoundingClientRect();
        const hits = (a, b) => !(a.bottom <= b.top || a.top >= b.bottom
                              || a.right <= b.left || a.left >= b.right);
        const l = () => box('map-legend');
        return ['panel', 'right-panel', 'log-panel'].filter(id => hits(l(), box(id)));
    }""")
    assert overlaps == [], f"key overlaps {overlaps}"

    page.click("#tools-btn")
    page.wait_for_selector("#right-panel.open")
    page.click('button[data-action="toggleLog"]')
    page.wait_for_selector("#log-panel.open")
    page.wait_for_timeout(400)

    overlaps = page.evaluate("""() => {
        const box = id => document.getElementById(id).getBoundingClientRect();
        const hits = (a, b) => !(a.bottom <= b.top || a.top >= b.bottom
                              || a.right <= b.left || a.left >= b.right);
        const l = () => box('map-legend');
        return ['panel', 'right-panel', 'log-panel'].filter(id => hits(l(), box(id)));
    }""")
    assert overlaps == [], f"with both panels open, key overlaps {overlaps}"
