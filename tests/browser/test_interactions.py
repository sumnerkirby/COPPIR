"""Handler wiring: the delegated dispatcher and the things it replaced.

Each of these covers a bug that reached main, or behaviour that broke while the
frontend was being pulled apart.

Note the selectors: several controls live in panels parked off-screen until
opened, and `button[data-action=...]` is often needed because a panel header
carries the same action as its toolbar button.
"""


def test_data_action_click_reaches_its_handler(app_page):
    """The delegated dispatcher, end to end.

    The log panel is always in the DOM at 34px and grows to 220px, so the
    signal is the `open` class rather than visibility.
    """
    panel = app_page.locator("#log-panel")
    app_page.click('button[data-action="toggleLog"]')
    app_page.wait_for_selector("#log-panel.open")
    assert "open" in (panel.get_attribute("class") or "")

    app_page.click('button[data-action="toggleLog"]')
    app_page.wait_for_timeout(300)
    assert "open" not in (panel.get_attribute("class") or "")


def test_data_action_passes_arguments(right_panel):
    """data-args is JSON now, not arguments spliced into a string of JS."""
    page = right_panel
    page.click('[data-action="setMarkupColor"][data-args*="FFAA00"]')
    page.wait_for_timeout(250)
    active = page.locator(".markup-swatch.swatch-active")
    assert active.count() == 1
    assert active.get_attribute("data-color") == "#FFAA00"


def test_enter_in_location_search_runs_a_search(app_page):
    """Regression: this was onkeydown="if(e.key==='Enter')geoSearch()".

    Inline handlers are given `event`, not `e`, so it threw ReferenceError on
    every keypress and Enter never searched. Stub the network call and check
    the handler is reached at all.
    """
    app_page.evaluate("""() => {
        window.__searched = false;
        const orig = window.fetch;
        window.fetch = (url, ...rest) => {
            if (String(url).includes('/api/geocode')) {
                window.__searched = true;
                return Promise.resolve(new Response('[]', {
                    status: 200, headers: { 'Content-Type': 'application/json' } }));
            }
            return orig(url, ...rest);
        };
    }""")
    app_page.fill("#loc-input", "Washington DC")
    app_page.press("#loc-input", "Enter")
    app_page.wait_for_timeout(500)
    assert app_page.evaluate("() => window.__searched") is True


def test_starting_a_shape_stops_an_active_measurement(right_panel):
    """maptools.js is one module because these two have to cancel each other."""
    page = right_panel
    page.click("#measure-btn")
    page.wait_for_selector("#measure-btn.btn-active")

    page.click("#draw-rect-btn")
    page.wait_for_timeout(400)
    assert "btn-active" not in (page.get_attribute("#measure-btn", "class") or "")

    page.keyboard.press("Escape")
    page.wait_for_timeout(250)


def test_escape_cancels_a_part_drawn_shape(right_panel):
    """Exercises cancelActiveDraw(), the accessor app.js uses to reach maptools."""
    page = right_panel
    page.click("#draw-rect-btn")
    page.wait_for_selector("#draw-rect-btn.btn-active")

    page.keyboard.press("Escape")
    page.wait_for_timeout(350)
    assert "btn-active" not in (page.get_attribute("#draw-rect-btn", "class") or "")


def test_map_lock_toggles_label_and_state(right_panel):
    """map.js owns the lock; the button is how you can tell from outside."""
    page = right_panel
    page.click("#map-lock-btn")
    page.wait_for_timeout(250)
    assert page.inner_text("#map-lock-btn").strip() == "LOCKED"

    page.click("#map-lock-btn")
    page.wait_for_timeout(250)
    assert page.inner_text("#map-lock-btn").strip() == "LOCK MAP"


def test_exercise_timer_counts_and_resets(right_panel):
    """timer.js owns four values; nothing outside it should be able to tell."""
    page = right_panel
    page.click('[data-action="toggleTimer"]')
    page.wait_for_timeout(2200)
    running = page.inner_text("#timer-display").strip()
    page.click('[data-action="toggleTimer"]')
    page.click('[data-action="resetTimer"]')
    page.wait_for_timeout(300)

    assert running != "00:00:00", "timer should have advanced"
    assert page.inner_text("#timer-display").strip() == "00:00:00"


def test_custom_metric_add_adjust_delete(app_page):
    """metrics.js keeps its list module-private and backed by localStorage."""
    app_page.click('[data-action="toggleMetricsPanel"]')
    app_page.wait_for_selector("#metrics-panel.open")
    app_page.fill("#met-name", "Comms Readiness")
    app_page.fill("#met-val", "40")
    app_page.click('[data-action="addMetric"]')
    app_page.wait_for_selector(".metric-wheel-wrap")
    assert app_page.locator(".metric-wheel-wrap").count() == 1

    app_page.click('[data-action="adjustMetric"][data-args$=",5]"]')
    app_page.wait_for_timeout(300)
    assert "45%" in app_page.inner_text(".metric-wheel-wrap")

    app_page.click('[data-action="deleteMetric"]')
    app_page.wait_for_timeout(300)
    assert app_page.locator(".metric-wheel-wrap").count() == 0


def test_filtering_dims_non_matching_pins(seeded, app_page):
    app_page.fill("#pin-filter-inp", "Rosslyn")
    app_page.wait_for_timeout(600)
    dimmed = app_page.evaluate("""() =>
        [...document.querySelectorAll('.leaflet-marker-icon')]
          .filter(el => parseFloat(getComputedStyle(el).opacity) < 0.5).length
    """)
    assert dimmed == 4, "one of the five seeded pins matches 'Rosslyn'"
