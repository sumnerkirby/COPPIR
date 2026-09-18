"""The tools panel holds more than fits, so order and folding both matter."""


def _sections(page):
    return page.evaluate("""() => {
        const rp = document.getElementById('right-panel');
        return [...rp.querySelectorAll('.panel-section[data-section]')].map(s => ({
            key: s.dataset.section,
            offset: Math.round(s.offsetTop - rp.offsetTop),
        }));
    }""")


def test_inject_queue_sits_above_the_fold(right_panel, seeded):
    """It used to start 917px down a 654px viewport, behind the standing
    configuration and a block of static help text."""
    page = right_panel
    viewport = page.evaluate("() => document.getElementById('right-panel').clientHeight")
    offsets = {s["key"]: s["offset"] for s in _sections(page)}

    assert offsets["injects"] < viewport, \
        f"inject queue starts at {offsets['injects']}px in a {viewport}px panel"
    assert offsets["injects"] < offsets["markup"]
    assert offsets["injects"] < offsets["thresholds"]
    assert offsets["find"] < offsets["markup"]


def test_sections_fold_and_the_choice_sticks(right_panel):
    page = right_panel
    section = "#right-panel .panel-section[data-section='markup']"
    assert page.locator("#measure-btn").is_visible()

    page.click(f"{section} .section-hdr")
    page.wait_for_selector(f"{section}.collapsed")
    assert not page.locator("#measure-btn").is_visible()

    page.reload(wait_until="networkidle")
    page.click("#tools-btn")
    page.wait_for_selector("#right-panel.open")
    assert page.locator(f"{section}.collapsed").count() == 1, "fold did not persist"

    page.click(f"{section} .section-hdr")
    page.wait_for_selector(f"{section}:not(.collapsed)")


def test_the_inject_queue_header_button_does_not_fold_it(right_panel):
    """The + NEW button lives inside the clickable header."""
    page = right_panel
    page.click('button[data-action="openInjectModal"]')
    page.wait_for_selector("#create-inject-modal", state="visible")
    assert page.locator("#right-panel .panel-section[data-section='injects'].collapsed").count() == 0
    page.keyboard.press("Escape")
