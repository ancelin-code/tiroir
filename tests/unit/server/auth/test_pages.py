import pytest

from tiroir.server.auth.pages import SIGNIN_PATH, _form_target, safe_next


@pytest.mark.parametrize(
    "value",
    ["/oauth/authorize?consent=abc", "/signin", "/x"],
)
def test_local_path_is_kept(value: str) -> None:
    # Given
    next_path = value

    # When
    kept = safe_next(next_path)

    # Then
    assert kept == value


@pytest.mark.parametrize(
    "value",
    [None, "", "https://attacker.example/", "//attacker.example/", "/\\attacker", "x"],
)
def test_other_target_falls_back_to_sign_in(value: object) -> None:
    # Given
    next_path = value

    # When
    kept = safe_next(next_path)

    # Then
    assert kept == SIGNIN_PATH


@pytest.mark.parametrize(
    ("redirect_uri", "source"),
    [
        ("http://127.0.0.1:33418/callback", " http://127.0.0.1:33418"),
        ("https://claude.ai/api/mcp/auth_callback", " https://claude.ai"),
        ("cursor://anysphere.cursor-mcp/oauth/callback", ""),
        ("com.example.app:/callback", " com.example.app:"),
        ("https://a.example;script-src*/cb", ""),
        ("javascript://a.example/%0aalert(1)", ""),
        ("data:text/html,x", ""),
        ("http://attacker.example/cb", ""),
        ("https://a.example/cb#f", ""),
    ],
)
def test_form_target_allows_only_the_redirect_origin(
    redirect_uri: str, source: str
) -> None:
    # Given
    uri = redirect_uri

    # When
    target = _form_target(uri)

    # Then
    assert target == source
