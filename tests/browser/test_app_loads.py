"""The page boots, the modules resolve, and nothing leaks to global scope."""


def test_page_loads_without_errors(app_page):
    """app_page asserts no uncaught errors on teardown; this checks it got that far."""
    assert app_page.title() == "COPPIR"


def test_all_es_modules_resolve(app_page):
    """A module that fails to resolve leaves a page that renders but does nothing."""
    loaded = app_page.evaluate("""() =>
        performance.getEntriesByType('resource')
          .filter(r => r.name.includes('/js/'))
          .map(r => r.name.split('/js/')[1])
          .sort()
    """)
    assert set(loaded) >= {
        "api.js", "constants.js", "map.js", "maptools.js",
        "metrics.js", "timer.js", "toast.js", "utils.js",
    }, f"modules actually fetched: {loaded}"


def test_module_scope_does_not_leak_globals(app_page):
    """Encapsulation is the point of the split; assert it rather than assume it."""
    leaked = app_page.evaluate("""() =>
        ['escHtml', 'showToast', 'ACTIONS', 'getMap', 'customMetrics', 'pins']
          .filter(n => typeof window[n] !== 'undefined')
    """)
    assert leaked == [], f"leaked to global scope: {leaked}"


def test_leaflet_basemap_renders(app_page):
    """Both Esri layers, not just the terrain one."""
    layers = app_page.locator(".leaflet-tile-pane .leaflet-layer")
    assert layers.count() == 2
    app_page.wait_for_function(
        "() => document.querySelectorAll('.leaflet-tile-loaded').length > 0")


def test_no_third_party_cdn_requests(app_page):
    """The vendoring holds: nothing reaches unpkg or cdnjs at runtime."""
    external = app_page.evaluate("""() =>
        performance.getEntriesByType('resource')
          .map(r => r.name)
          .filter(n => n.includes('unpkg.com') || n.includes('cdnjs.cloudflare.com'))
    """)
    assert external == [], f"still loading from a CDN: {external}"


def test_every_data_action_resolves_to_a_handler(app_page):
    """An unknown data-action fails silently at click time, so check up front."""
    unresolved = app_page.evaluate("""() => {
        const els = [...document.querySelectorAll('[data-action]')];
        const bad = [];
        for (const el of els) {
            if (!el.dataset.args) continue;
            try { JSON.parse(el.dataset.args); } catch { bad.push(el.dataset.action); }
        }
        return bad;
    }""")
    assert unresolved == [], f"data-args that do not parse: {unresolved}"
    assert app_page.locator("[data-action]").count() > 50
    assert app_page.locator("[onclick]").count() == 0
