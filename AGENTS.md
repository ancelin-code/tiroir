<!-- delivery-kit:routing -->
## Delivery Kit

This project is delivered with Delivery Kit. Its state lives in `delivery/`
and in git, never in a conversation.

Route every request about this project through the `delivery-orchestrator`
skill before reading files or running commands: what to build or change, what
to do next, where the project stands, who is working on what. Only requests
unrelated to delivering this project skip it.
<!-- /delivery-kit:routing -->

## Language

All repository content is written in English: specifications (`delivery/`),
decision records, documentation, code, comments and commit messages. The only
exception is user-facing memory content, whose language is a store setting
(for example French for the `accounting-firm` preset's synthetic data).

## Tests

Tests are either unit or integration tests, and live in the matching folder:

- `tests/unit/`: pure logic, with no SQLite, Git, network or subprocess, and
  nothing written to disk (reading a fixture file kept under `tests/` is fine). Mirrors `src/tiroir/`, one file per module:
  `src/tiroir/core/layout.py` is tested by `tests/unit/core/test_layout.py`.
  They are fast: `mise run test:unit`.
- `tests/integration/`: anything that touches the real thing: SQLite, bare Git
  repositories, files, the web application (Starlette's test client), a
  command run through `main()`. Named after the feature, flat:
  `tests/integration/test_admin_members.py`. Use the real components in
  `tmp_path`; do not mock SQLite or Git.
- A module with both pure logic and I/O has a file in each folder. A test that
  needs the database to mean anything is an integration test, however small.

Every test is laid out in three blocks, each opened by a comment: `# Given`
(the setup), `# When` (the one action under test) and `# Then` (the
assertions). Keep the action out of the assertions: call it under `# When`,
store its result, and assert on that result under `# Then`. A test with no
setup still has its `# Given`, stating what the inputs are. Property-based
tests (`hypothesis`) follow the same layout inside the test body.

```python
def test_unknown_argument_fails(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    argv = ["bogus"]

    # When
    code = main(argv)

    # Then
    assert code == 2
    assert capsys.readouterr().err.startswith("usage: tiroir")
```

## Logs

No `print` anywhere (ruff `T20`): use `from loguru import logger`, including
for what a command shows the user (`logger.info` to stdout, `logger.error` to
stderr, set up by `tiroir.cli.main.setup_logging`). Never log memory content
(Y5): identifiers, codes and counts only.

## Command line

The `tiroir` command is parsed with `argparse` (ADR-002), one sub-parser per
command group of [the CLI contract](delivery/contracts/cli.md). No other
argument parsing library.

## Docstrings

Give functions, methods and classes a docstring of one or two lines that says
what they are for and, where it is not obvious, what they return or raise.
Skip it only where the name and signature already say everything (a test, a
dunder method, a one-line accessor).
