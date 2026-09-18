"""The SITREP strip: sector arithmetic, threshold badges, and its layout.

The seeded scenario is built so the percentages are exact: two Compromised
power assets (0), two Clean hospitals (100), one Monitored bank (70).
"""
import pytest


def test_status_counts(seeded, app_page):
    app_page.wait_for_function("() => document.getElementById('cnt-total').textContent === '5'")
    assert app_page.inner_text("#cnt-comp") == "2"
    assert app_page.inner_text("#cnt-cln") == "2"
    assert app_page.inner_text("#cnt-mon") == "1"


@pytest.mark.parametrize("sector,expected", [
    ("power", "0%"),
    ("medical", "100%"),
    ("financial", "70%"),
])
def test_sector_integrity_is_the_mean_of_its_pins(seeded, app_page, sector, expected):
    app_page.wait_for_function(
        f"() => document.querySelector('#ww-{sector} .pct-text')?.textContent === '{expected}'")


def test_threshold_badge_fires_only_below_its_level(seeded, app_page):
    """Power is 0% against a 50% threshold; the others have no rule at all."""
    app_page.wait_for_selector("#ww-power .wheel-alert")
    assert app_page.locator("#ww-medical .wheel-alert").count() == 0
    assert app_page.locator("#ww-financial .wheel-alert").count() == 0


def test_sectors_with_no_assets_read_as_empty(seeded, app_page):
    """Nothing was seeded for government, so it must not read as 0% integrity.

    Note .pct-text is an SVG <text> node, so it needs text_content() -- inner_text
    only works on HTMLElements.
    """
    app_page.wait_for_function("() => document.getElementById('cnt-total').textContent === '5'")
    government = app_page.locator("#ww-government .pct-text").text_content().strip()
    assert government != "0%", "an empty sector must not read as total failure"


class TestStripLayout:
    """Regression: at the smallest window run.py allows, the last three sector
    wheels ran off the right-hand edge with no scrollbar to reveal them."""

    @pytest.mark.parametrize("width", [1440, 1200, 1100])
    def test_every_sector_wheel_fits_on_screen(self, seeded, app_page, width):
        app_page.set_viewport_size({"width": width, "height": 800})
        app_page.wait_for_timeout(400)

        overflow = app_page.evaluate("""() => {
            const wheels = [...document.querySelectorAll('.wheel-wrap')];
            return wheels
              .filter(w => w.getBoundingClientRect().right > window.innerWidth)
              .map(w => w.id);
        }""")
        assert overflow == [], f"wheels past the right edge at {width}px: {overflow}"

    def test_strip_does_not_overflow_at_minimum_width(self, seeded, app_page):
        app_page.set_viewport_size({"width": 1100, "height": 700})
        app_page.wait_for_timeout(400)
        assert app_page.evaluate("""() => {
            const m = document.getElementById('sitrep-metrics');
            return m.scrollWidth <= m.clientWidth;
        }"""), "SITREP metrics row still overflows at the minimum window width"

    def test_all_six_sectors_are_present(self, app_page):
        assert app_page.locator(".wheel-wrap").count() == 6
