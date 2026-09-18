"""Destructive actions ask in the app, not through native browser dialogs.

A native confirm() would block the page and never reach Playwright's DOM at
all, so these tests only pass against the in-app modal.
"""


def _dialog_would_block(page):
    """Fail loudly if anything still reaches for window.confirm/prompt."""
    page.evaluate("""() => {
        window.__native = 0;
        window.confirm = () => { window.__native++; return false; };
        window.prompt  = () => { window.__native++; return null; };
    }""")


def test_delete_all_pins_confirms_in_app(app_page, seeded, api):
    page = app_page
    _dialog_would_block(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length >= 5")

    page.click('[data-action="clearAllPinsConfirm"]')
    page.wait_for_selector("#ask-modal", state="visible")
    assert "DELETE ALL PINS" in page.text_content("#ask-hdr")
    assert "cannot be undone" in page.text_content("#ask-message")

    page.click('[data-action="resolveAsk"][data-args="[false]"]')
    page.wait_for_selector("#ask-modal", state="hidden")
    assert len(api.get("/api/pins").json()) == 5, "cancel must not delete"

    page.click('[data-action="clearAllPinsConfirm"]')
    page.wait_for_selector("#ask-modal", state="visible")
    page.click("#ask-ok")
    page.wait_for_selector("#ask-modal", state="hidden")
    page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length === 0")

    assert page.evaluate("() => window.__native") == 0, "still using a native dialog"


def test_escape_cancels_the_dialog(app_page, seeded, api):
    page = app_page
    _dialog_would_block(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-marker-icon').length >= 5")

    page.click('[data-action="clearAllPinsConfirm"]')
    page.wait_for_selector("#ask-modal", state="visible")
    page.keyboard.press("Escape")
    page.wait_for_selector("#ask-modal", state="hidden")
    assert len(api.get("/api/pins").json()) == 5


def test_metric_value_is_asked_for_in_app(app_page):
    page = app_page
    _dialog_would_block(page)

    page.click("#metrics-btn")
    page.fill("#met-name", "Comms uptime")
    page.fill("#met-val", "80")
    page.click('[data-action="addMetric"]')
    page.wait_for_selector(".metric-wheel-wrap")

    page.click(".metric-wheel-wrap .wheel-svg")
    page.wait_for_selector("#ask-modal", state="visible")
    assert page.input_value("#ask-input") == "80"

    page.fill("#ask-input", "45")
    page.press("#ask-input", "Enter")
    page.wait_for_selector("#ask-modal", state="hidden")
    page.wait_for_function(
        "() => document.querySelector('.metric-wheel-wrap .pct-text, .metric-wheel-wrap text')"
        "?.textContent === '45%'")

    assert page.evaluate("() => window.__native") == 0
    page.evaluate("() => localStorage.removeItem('coppir_metrics')")
