---
id: foundation-001
title: Bootstrap the Python project, its tooling and CI
type: build
epic: foundation
depends_on: []
parallel: false
conflicts_with: []
tier: build
review: []
---

## Context

The repository holds only documentation. Every later task needs the same
Python project, layout, commands and checks, decided in
[ADR-002](../decisions/ADR-002-python-and-container-distribution.md) (Python
3.13, `mise`, `uv`, `ruff`, `pyrefly`, `pytest`, `import-linter`) and
[ADR-013](../decisions/ADR-013-adapters-and-skills.md) (package layout and
dependency rule). This task runs alone because it creates the lock file and
the layout everything else edits.

## Covers

- U5 (part): the `import-linter` contracts that keep `tiroir.core` free of any
  surface or host import, checked in CI; the core's content comes later
- D1 (part): CI on Linux for the server; the adapter checks on macOS and
  Windows come with the plugin (retrieval milestone)
- D3

## Scope

Files this task is expected to touch:

- `mise.toml`: tools (Python 3.13, `uv`) and tasks `lint`, `format`,
  `typecheck`, `test`, `check` (all of them), `serve`
- `pyproject.toml`, `uv.lock`: package `tiroir`, `src/` layout, Apache-2.0
  licence metadata, console script `tiroir = "tiroir.cli.main:main"`
- `src/tiroir/__init__.py`, `src/tiroir/core/__init__.py`,
  `src/tiroir/server/__init__.py`, `src/tiroir/cli/__init__.py`,
  `src/tiroir/cli/main.py` (an entry point printing usage and the version),
  `src/tiroir/adapters/__init__.py`
- `tests/conftest.py`, `tests/test_smoke.py`
- `.github/workflows/ci.yml`
- `.gitignore` (add `.venv/`, `__pycache__/`, `.pytest_cache/`, `/data/`)

Runtime dependencies to declare now, so that no later task of this milestone
edits the lock file: `mcp`, `starlette`, `uvicorn`, `jinja2`,
`python-multipart`, `ruamel.yaml`, `pygit2`, `PyStemmer`, `argon2-cffi`,
`httpx`. Development dependencies: `ruff`, `pyrefly`, `pytest`,
`hypothesis`, `import-linter`, `pip-audit`.

Out of scope:

- any tiroir behaviour beyond the entry point printing usage and version
- the embedding, NumPy and `pyahocorasick` dependencies (retrieval milestone)
- the container image and its CI workflow (`deploy-001`)

## Acceptance criteria

- `mise install && mise run check` succeeds on a fresh clone: ruff lint and
  format check, `pyrefly check` with `preset = "strict"` configured in
  `pyproject.toml`, `lint-imports`, and `pytest`.
- `uv run tiroir --version` prints the package version.
- `import-linter` contracts exist and pass: `tiroir.core` imports none of
  `tiroir.server`, `tiroir.cli`, `tiroir.adapters`; `tiroir.cli` does not
  import `tiroir.server` or `tiroir.adapters`; `tiroir.server` and
  `tiroir.adapters` do not import each other. A deliberate forbidden import in
  a scratch branch makes `mise run check` fail (state it in the pull request).
- The CI workflow runs `mise run check` on Linux on every pull request and on
  pushes to `develop`, and also runs `pip-audit` on the lock file.
- `uv.lock` is committed and `uv sync --frozen` works from it.

## Validation

`mise run check`, and the CI run of the pull request.
