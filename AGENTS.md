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

## Output and logs

`print` is banned (ruff `T20`), as
[ADR-002](delivery/decisions/ADR-002-python-and-container-distribution.md)
records:

- a command's own output (results, usage, CLI error lines) goes through
  `tiroir.cli.output`: `out()` for stdout, `err()` for stderr;
- everything else is a log: `from loguru import logger`, then
  `logger.debug/info/warning/error(...)`;
- no log line, error message or commit message carries memory content (Y5):
  log identifiers, codes and counts, never the text of a note or a query.
