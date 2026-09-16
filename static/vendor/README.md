# Vendored frontend dependencies

These are third-party libraries, committed rather than pulled from a CDN at
runtime. The app is meant to run on a single machine during an exercise, and
depending on unpkg and cdnjs being reachable at that moment defeated the point.
It also means a PyInstaller build is genuinely self-contained, and that no
third-party host sees a request every time the app opens.

Nothing here is modified. To update a library, replace the files from the same
source URL and bump the version below.

| Library | Version | License | Source |
|---|---|---|---|
| Leaflet | 1.9.4 | BSD-2-Clause | `https://unpkg.com/leaflet@1.9.4/dist/` |
| Leaflet.markercluster | 1.5.3 | MIT | `https://unpkg.com/leaflet.markercluster@1.5.3/dist/` |
| Leaflet.heat | 0.2.0 | BSD-2-Clause | `https://unpkg.com/leaflet.heat@0.2.0/dist/` |
| Leaflet.draw | 1.0.4 | MIT | `https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/` |
| Font Awesome Free | 6.5.1 | CC BY 4.0 (icons), SIL OFL 1.1 (fonts), MIT (code) | `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/` |

## Notes

Only Font Awesome's Solid style is vendored. Every icon the app uses is solid,
so `fontawesome.min.css` plus `solid.min.css` and `fa-solid-900.woff2` covers
it; the regular and brands styles would be another ~400KB for nothing.

`solid.min.css` lists a `.ttf` after the `.woff2` as a fallback. It is not
vendored. Browsers take the first format they support and never request the
second, and every platform pywebview targets (WebKit, WebView2, WebKit2GTK)
has supported woff2 for years.

The Leaflet.draw sprites are here because `leaflet.draw.css` references them,
though in practice the app draws with its own MAP MARKUP toolbar rather than
Leaflet.draw's built-in one, so they are rarely requested.

## What still needs the network

Vendoring covers the frontend code. The app still reaches out for map tiles
(Esri), geocoding (Nominatim) and infrastructure lookups (Overpass). Without a
connection the interface loads and works; the map behind it is blank.
