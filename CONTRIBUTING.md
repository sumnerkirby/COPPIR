# Contributing to COPPIR

COPPIR is currently maintained by a single developer, but it follows a
branch-and-pull-request workflow so that every change is reviewable in
isolation and the history stays readable.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

`run.py` opens the desktop window and starts the FastAPI server on
`localhost:8000`. See [ARCHITECTURE.md](ARCHITECTURE.md) for how the two
layers fit together.

## Branches

`main` is always releasable. Work happens on short-lived topic branches
named `<type>/<short-description>`:

```
feat/vendor-leaflet-assets
fix/osm-null-island-coordinates
chore/remove-legacy-prototype
docs/threat-model
```

Use the same `<type>` vocabulary as commit messages (below).

## Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <summary in the imperative mood>

<body — what changed and, more importantly, why>
```

| Type | Use for |
|---|---|
| `feat` | A new user-facing capability |
| `fix` | A bug fix |
| `refactor` | Restructuring with no behavior change |
| `perf` | A change made for performance |
| `docs` | Documentation only |
| `test` | Tests only |
| `build` | Packaging, dependencies, PyInstaller spec |
| `chore` | Repo housekeeping that fits nothing above |

Keep the summary under ~72 characters and in the imperative mood ("add
vendored Leaflet", not "added" or "adds"). The body is where the reasoning
goes; prefer explaining *why* over restating the diff.

## Pull requests

- One logical change per PR. If a PR needs the word "and" to describe it,
  it is probably two PRs.
- Fill in the PR template: what changed, why, and how it was verified.
- Link any related issue with `Closes #<n>`.
- Squash-merge into `main` so each merge is one coherent commit.

## Verifying a change

There is no automated test suite yet (adding one is tracked work). Until
there is, state in the PR description how the change was exercised
manually — which screens or endpoints were touched and what was observed.
