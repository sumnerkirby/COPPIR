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

There is no test suite yet, so until there is, note in the PR how the change
was exercised by hand.
