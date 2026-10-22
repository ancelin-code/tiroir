from importlib.metadata import version

import pytest

from tiroir.cli.main import main


def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    expected = version("tiroir")

    # When
    code = main(["--version"])

    # Then
    assert code == 0
    assert capsys.readouterr().out.strip() == expected


def test_no_arguments_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    argv: list[str] = []

    # When
    code = main(argv)

    # Then
    assert code == 0
    assert capsys.readouterr().out.startswith("usage: tiroir")


def test_unknown_argument_fails(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    argv = ["bogus"]

    # When
    code = main(argv)

    # Then
    assert code == 2
    assert "usage: tiroir" in capsys.readouterr().out
