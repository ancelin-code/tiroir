import pytest

from tiroir.cli.main import main


def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    from importlib.metadata import version

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == version("tiroir")


def test_no_arguments_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert capsys.readouterr().out.startswith("usage: tiroir")


def test_unknown_argument_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["bogus"]) == 2
    assert "usage: tiroir" in capsys.readouterr().out
