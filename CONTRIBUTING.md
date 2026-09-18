# Contributing

This is a one-person project, but it uses a branch-and-PR workflow anyway so
that each change is reviewable on its own and the history stays readable.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

That opens the desktop window and starts the FastAPI server on localhost:8000.
[ARCHITECTURE.md](ARCHITECTURE.md) covers how the two halves fit together.

To work against a populated map instead of an empty one, run
`python examples/seed_demo.py` in a second shell.

## Branches and commits

`main` stays releasable. Work happens on short branches named
`type/short-description`, like `fix/osm-null-island-coordinates` or
`docs/threat-model`.

Commit subjects use the same `type:` prefix and the imperative mood, e.g.
`fix: cap OSM results at 200`. The useful types here are `feat`, `fix`,
`refactor`, `perf`, `docs`, `test`, `build`, and `chore`. Put the reasoning in
the body when a change isn't self-explanatory; skip the body when it is.

## Pull requests

One logical change per PR. Say what changed, why, and how you checked it.
Squash on merge.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

There are two suites.

`tests/` drives the API through FastAPI's `TestClient` -- no server, no network,
runs in under a second. State lives in module-level containers in `state.py`,
so `tests/conftest.py` clears them between tests and points scenario writes at
a temp directory.

`tests/browser/` drives a real Chromium against a real server, because some
things are only observable there: ES module wiring, the `data-action`
dispatcher, Leaflet rendering, websocket updates landing in an open page, and
CSS layout at a given window size. It needs one extra step:

```bash
playwright install chromium
```

Without that the browser tests skip with a message rather than failing. They
take around 40 seconds against under a second for the API suite, so CI runs
them as a separate job -- `pytest --ignore=tests/browser` is the fast loop.

The browser fixtures assert that no uncaught JS error occurred during a test.
That is deliberate: the usual frontend failure here is silent, leaving a page
that looks nearly right.

Coverage is partial. If you touch something neither suite reaches, say in the
PR how you checked it by hand.
