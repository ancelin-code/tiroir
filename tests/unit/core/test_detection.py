"""Name tokens, n-gram matching, ambiguity and the working-directory rule."""

import time

from hypothesis import given
from hypothesis import strategies as st

from tiroir.core.detection import NameDictionary, detect, name_tokens
from tiroir.core.lexical import DrawerRef

FIRM = "firm"
BAKERY = DrawerRef(FIRM, "clients/c001")
OTHER = DrawerRef(FIRM, "clients/c002")
NO_CWD: dict[str, list[str]] = {}


def dictionary(*names: tuple[str, str], store: str = FIRM) -> NameDictionary:
    """A dictionary of `(drawer, name)` pairs."""
    return NameDictionary.build(store, names)


def test_name_tokens_fold_and_split_on_punctuation() -> None:
    # Given
    text = "BOULANGERIE-Bérenger, l'œuvre_2"

    # When
    tokens = name_tokens(text)

    # Then
    assert tokens == ["boulangerie", "berenger", "l", "oeuvre", "2"]


def test_name_tokens_keep_stop_words_and_do_not_stem() -> None:
    # Given
    text = "les déclarations de la société"

    # When
    tokens = name_tokens(text)

    # Then
    assert tokens == ["les", "declarations", "de", "la", "societe"]


def test_a_name_matches_whatever_its_case_punctuation_or_accents() -> None:
    # Given
    names = dictionary(("clients/c001", "Boulangerie Bérenger"))
    texts = [
        "Relance Boulangerie Bérenger",
        "BOULANGERIE-BERENGER",
        "boulangerie  bérenger",
    ]

    # When
    results = [detect(t, None, [names], NO_CWD) for t in texts]

    # Then
    assert [[d.drawer for d in found] for found, _ in results] == [[BAKERY]] * 3
    assert [found[0].matched for found, _ in results] == [
        "Boulangerie Bérenger",
        "BOULANGERIE-BERENGER",
        "boulangerie  bérenger",
    ]
    assert all(found[0].via == "name" for found, _ in results)
    assert all(ambiguities == () for _, ambiguities in results)


def test_a_name_matches_on_token_boundaries_only() -> None:
    # Given
    names = dictionary(("clients/c001", "Dupont"))

    # When
    found, ambiguities = detect("Dupontel et superdupont", None, [names], NO_CWD)

    # Then
    assert found == () and ambiguities == ()


def test_the_matched_text_stops_at_an_underscore() -> None:
    # Given
    names = dictionary(("clients/c001", "Bérenger"))

    # When
    found, _ = detect("dossier_Bérenger_2026", None, [names], NO_CWD)

    # Then
    assert [(d.drawer, d.matched) for d in found] == [(BAKERY, "Bérenger")]


def test_a_prompt_naming_two_drawers_detects_both() -> None:
    # Given
    names = dictionary(("clients/c001", "Bérenger"), ("clients/c002", "Thévenet"))

    # When
    found, _ = detect("Compare Thévenet et Bérenger", None, [names], NO_CWD)

    # Then
    assert {d.drawer for d in found} == {BAKERY, OTHER}


def test_a_drawer_named_twice_is_detected_once() -> None:
    # Given
    names = dictionary(("clients/c001", "Bérenger"), ("clients/c001", "C001"))

    # When
    found, _ = detect("C001 alias Bérenger", None, [names], NO_CWD)

    # Then
    assert [d.drawer for d in found] == [BAKERY]


def test_the_longer_name_wins_over_the_one_it_contains() -> None:
    # Given
    names = dictionary(
        ("clients/c001", "Boulangerie Dupont"), ("clients/c002", "Dupont")
    )

    # When
    found, ambiguities = detect("Pour Boulangerie Dupont", None, [names], NO_CWD)

    # Then
    assert [(d.drawer, d.matched) for d in found] == [(BAKERY, "Boulangerie Dupont")]
    assert ambiguities == ()


def test_the_shorter_name_still_matches_alone() -> None:
    # Given
    names = dictionary(
        ("clients/c001", "Boulangerie Dupont"), ("clients/c002", "Dupont")
    )

    # When
    found, _ = detect("Pour Dupont", None, [names], NO_CWD)

    # Then
    assert [d.drawer for d in found] == [OTHER]


def test_a_name_of_two_drawers_is_an_ambiguity_and_detects_none() -> None:
    # Given
    names = dictionary(("clients/c001", "Dupont"), ("clients/c002", "dupont"))

    # When
    found, ambiguities = detect("Appeler DUPONT", None, [names], NO_CWD)

    # Then
    assert found == ()
    assert [(a.matched, a.candidates) for a in ambiguities] == [
        ("DUPONT", (BAKERY, OTHER))
    ]


def test_a_name_of_two_stores_is_an_ambiguity() -> None:
    # Given
    first = dictionary(("clients/c001", "Dupont"), store="a")
    second = dictionary(("clients/c009", "Dupont"), store="b")

    # When
    found, ambiguities = detect("Dupont", None, [first, second], NO_CWD)

    # Then
    assert found == ()
    assert [a.candidates for a in ambiguities] == [
        (DrawerRef("a", "clients/c001"), DrawerRef("b", "clients/c009"))
    ]


def cwd_dictionary() -> NameDictionary:
    """A store whose `repo` field holds the folder of its drawers."""
    return NameDictionary.build(
        FIRM,
        [],
        [("projects/gw", "repo", "API Gateway"), ("projects/web", "repo", "web-app")],
    )


def test_cwd_detects_the_deepest_matching_folder_on_posix_paths() -> None:
    # Given
    cwd = "/home/u/src/api-gateway/services"

    # When
    found, _ = detect("", cwd, [cwd_dictionary()], {FIRM: ["repo"]})

    # Then
    assert [(d.drawer, d.matched, d.via) for d in found] == [
        (DrawerRef(FIRM, "projects/gw"), "api-gateway", "cwd")
    ]


def test_cwd_detects_on_windows_paths() -> None:
    # Given
    cwd = "C:\\src\\api-gateway"

    # When
    found, _ = detect("", cwd, [cwd_dictionary()], {FIRM: ["repo"]})

    # Then
    assert [d.drawer for d in found] == [DrawerRef(FIRM, "projects/gw")]


def test_the_deepest_folder_wins() -> None:
    # Given
    cwd = "/src/api-gateway/web-app"

    # When
    found, _ = detect("", cwd, [cwd_dictionary()], {FIRM: ["repo"]})

    # Then
    assert [d.drawer for d in found] == [DrawerRef(FIRM, "projects/web")]


def test_cwd_without_a_matching_folder_detects_nothing() -> None:
    # Given
    cwd = "/home/u/src/other"

    # When
    found, ambiguities = detect("", cwd, [cwd_dictionary()], {FIRM: ["repo"]})

    # Then
    assert found == () and ambiguities == ()


def test_cwd_is_ignored_for_a_field_the_store_does_not_declare() -> None:
    # Given
    cwd = "/src/api-gateway"

    # When
    found, _ = detect("", cwd, [cwd_dictionary()], {FIRM: []})

    # Then
    assert found == ()


def test_a_folder_of_two_drawers_is_an_ambiguity() -> None:
    # Given
    shared = NameDictionary.build(
        FIRM, [], [("a", "repo", "api"), ("b", "repo", "API")]
    )

    # When
    found, ambiguities = detect("", "/src/api", [shared], {FIRM: ["repo"]})

    # Then
    assert found == ()
    assert [(a.candidates, a.via) for a in ambiguities] == [
        ((DrawerRef(FIRM, "a"), DrawerRef(FIRM, "b")), "cwd")
    ]


def test_a_name_and_the_cwd_of_one_drawer_give_one_detection() -> None:
    # Given
    both = NameDictionary.build(
        FIRM, [("projects/gw", "Gateway")], [("projects/gw", "repo", "api-gateway")]
    )

    # When
    found, _ = detect("the Gateway", "/src/api-gateway", [both], {FIRM: ["repo"]})

    # Then
    assert [(d.drawer, d.via) for d in found] == [
        (DrawerRef(FIRM, "projects/gw"), "name")
    ]


NAME_WORDS = ["alpha", "bravo", "charlie", "delta dupont", "echo"]
OTHER_WORDS = st.text(alphabet="fghijklmnpqrstuvwxz", min_size=1, max_size=8)


@given(words=st.lists(OTHER_WORDS, max_size=30))
def test_text_of_words_that_are_no_name_detects_nothing(words: list[str]) -> None:
    # Given
    names = dictionary(*((f"d/{i}", n) for i, n in enumerate(NAME_WORDS)))
    text = " ".join(words)

    # When
    found, ambiguities = detect(text, None, [names], NO_CWD)

    # Then
    assert found == () and ambiguities == ()


def test_detecting_in_a_long_prompt_over_a_large_dictionary_is_fast() -> None:
    # Given
    names = dictionary(*((f"d/{i}", f"Client{i} Société{i}") for i in range(2000)))
    text = " ".join(
        f"mot{i % 300}" if i % 50 else "Client7 Société7" for i in range(2000)
    )
    best = float("inf")

    # When
    for _ in range(5):
        started = time.perf_counter()
        found, _ = detect(text, None, [names], NO_CWD)
        best = min(best, time.perf_counter() - started)

    # Then
    assert [d.drawer for d in found] == [DrawerRef(FIRM, "d/7")]
    assert best < 0.020
