"""The two things a user takes out of an exercise: the log and the briefing."""


def test_briefing_saves_a_file_when_pop_ups_are_unavailable(app_page, seeded):
    """pywebview's backends do not all support window.open.

    This used to dead-end on a "pop-up blocked" toast, losing the briefing.
    """
    page = app_page
    page.evaluate("() => { window.open = () => null; }")

    with page.expect_download() as dl:
        page.click('[data-action="exportBriefing"]')
    assert dl.value.suggested_filename.startswith("coppir_sitrep_")
    assert dl.value.suggested_filename.endswith(".html")


def test_exported_log_quotes_fields_containing_commas(app_page, api):
    """Only two of the four columns were quoted, so a comma in an asset name
    shifted every column after it."""
    page = app_page
    api.post("/api/log", json={
        "action": "Rerouted feed, then isolated",
        "asset_name": "Substation 4, West",
        "notes": 'called it "clear"',
    }).raise_for_status()
    page.wait_for_function(
        "() => document.querySelectorAll('.log-entry').length > 0")

    with page.expect_download() as dl:
        page.click('[data-action="exportLog"]')
    text = dl.value.path().read_text()

    header, *rows = [r for r in text.splitlines() if r.strip()]
    assert header.count(",") == 3
    row = next(r for r in rows if "Substation 4" in r)
    # Four quoted fields, so the only bare commas are the three separators.
    assert row.count('","') == 3
    assert '"Substation 4, West"' in row
    assert '"called it ""clear"""' in row
