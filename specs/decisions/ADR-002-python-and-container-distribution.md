# ADR-002: Build the server in Python and ship it as a container image, under explicit lightness rules

**Status:** accepted
**Date:** 2026-10-22

## Context

tiroir v1 is a self-hosted server (A1), reached by hosts as a remote MCP
connector (U1, U4); nothing is installed on members' machines. The work that
costs memory and time is done by native engines whatever the language around
them: the embedding model (ONNX Runtime), the index (SQLite) and the history
(Git). The default embedding model must be the best one the evaluation finds
within the server budget (R4a, P4), the server must speak the MCP
authorization flow the Claude hosts use (A4), and the project owner reviews
the code. A Rust design was approved on 2026-10-21 for a binary installed on
every machine; the project owner moved to Python on 2026-10-22 when the
target became a server.

## Decision

- **Language:** Python 3.13, one package `tiroir` with sub-packages (layout
  and dependency rule in ADR-013).
- **Project tooling:**
  - `mise` pins the tool versions (Python, `uv`) in `mise.toml` and defines
    the project's tasks (`lint`, `typecheck`, `test`, `bench`, `image`), so a
    developer, a lane and CI run the same commands with the same versions;
  - `uv` manages the virtual environment and the dependencies, locked in
    `pyproject.toml` and `uv.lock`; the image installs from the lock file with
    `uv sync --frozen`.
- **Main dependencies:**
  - the official MCP Python SDK (`mcp`): streamable HTTP transport,
    elicitation, authorization-server support (ADR-015);
  - Starlette and Uvicorn: the one HTTP application serving MCP, the hook
    path, OAuth, the account and administration pages and Git (contract
    `http-routes.md`); Jinja2 for the pages;
  - `onnxruntime`, `tokenizers` and `huggingface_hub`: embeddings (ADR-006);
    `numpy`: vector search (ADR-005);
  - the standard library's `sqlite3` with FTS5 (ADR-005), `PyStemmer`
    (ADR-007), `pyahocorasick` (ADR-008), `ruamel.yaml` (ADR-003);
  - `pygit2`, plus the `git` executable and `git-filter-repo` in the image
    (ADR-010, ADR-011);
  - `argon2-cffi` (ADR-015), `httpx` (external embedding service, mirrors'
    HTTPS checks);
  - `loguru`: logging (below); pure Python, no dependency on Linux.
- **Logs:** `print` is banned everywhere, by ruff's `T20` rules; all output
  goes through loguru. The command line sets loguru up to write bare messages,
  INFO and below to stdout and WARNING and above to stderr, so a command's
  results and errors keep the streams of the CLI contract. Loguru is always
  configured with `diagnose=False` so tracebacks never show variable values,
  which could be memory content (Y5). The server writes JSON lines to stdout
  and routes the standard library loggers (Uvicorn, MCP SDK, httpx) into
  loguru.
- **Command line:** parsed with the standard library's `argparse`, one
  sub-parser per command group of the CLI contract (`tiroir admin members
  add`, …); no Click or Typer, which would add a dependency for what
  `argparse` already does, including the exit code 2 on a usage error.
- **Distribution:** one container image per release, `linux/amd64` and
  `linux/arm64`, built in GitHub Actions and published to the GitHub container
  registry with build provenance attestations, plus a `compose.yaml` that runs
  it behind Caddy for HTTPS (ADR-016). The image is the only supported way to
  run a server; `pip install tiroir` exists for development and tests.
- **Lightness rules**, checked in continuous integration and changed only by
  amending this record:
  - **No PyTorch, TensorFlow or CUDA** in the image: models run on ONNX
    Runtime, CPU.
  - **Image size:** ≤ 600 MB compressed, models excluded (they are downloaded
    into the data volume, ADR-006).
  - **Dependencies:** every runtime dependency is listed in this record with
    the reason for it; adding one means amending the record. Pure-Python or
    wheel-only packages are preferred; nothing compiles at install time.
  - **Budgets as tests:** P1–P4 and P7 are measured by a benchmark job on the
    reference server size, on every release and on demand; a regression fails
    the release.
  - **Escape hatch:** a hot path that a benchmark shows to break a budget may
    be rewritten as a native extension, in Rust through PyO3, behind the same
    Python interface. Never by default, only on a measurement.
- **Development:** `ruff` (lint and format), `pyrefly` for type checking with
  `preset = "strict"` on the whole package (configured in `pyproject.toml`),
  `pytest` with `hypothesis` for the property tests (X3, Y4g), `import-linter`
  for the dependency rule (ADR-013), `pip-audit` and a licence check of the
  locked dependencies (ADR-001). CI runs on Linux; the adapter checks of D1
  run on macOS, Windows and Linux.

## Alternatives considered

- **Rust** (the approved design of 2026-10-21) - one small binary, the least
  memory and the fastest code. Its main reason, installing a binary on every
  member's machine, is gone. In exchange: the embedding crates cover a fixed
  list of models, which conflicts with picking the best model by evaluation;
  the MCP authorization and OAuth pieces are less mature; the project owner
  reviews Python more easily. The heavy work runs in native engines either
  way, so the measured gain would be a few hundred megabytes of memory on a
  budget of 4 GB, and milliseconds against a network round trip of tens.
- **Python with PyTorch and `sentence-transformers`** - the widest model
  support, but an image of several gigabytes and more memory at rest, for
  models that also exist as ONNX exports.
- **Go** - small binaries and a good HTTP stack, but the embedding and
  tokenizer libraries are reached through cgo, and no mature MCP
  authorization-server library exists.
- **TypeScript on Node** - the reference MCP SDK, but weaker local inference,
  stemming and Git libraries than Python.
- **`mypy` for type checking** - the reference checker, but much slower on a
  whole project; `pyrefly` checks the package in seconds, so it runs on every
  save and every lane, and its strict preset covers the same ground.
- **`uv` alone, without `mise`** - `uv` can pin Python too, but not other
  tools or tasks; `mise` gives one entry point for every command lanes and CI
  run.

## Consequences

The server is heavier at rest than a Rust binary would be (about 150 MB for the
interpreter and libraries), which P4 absorbs. The lightness rules turn "light"
into checks a pull request can fail. Members install nothing, so the signing,
notarisation and per-platform build matrix of the Rust design are gone; the
container build and its two architectures replace them. The latency and memory
figures in ADR-006 and ADR-009 are measured on the reference server in the
first milestone and the records updated if they move.
