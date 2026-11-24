"""Detection over stores created from the accounting-firm preset."""

from pathlib import Path

from conftest import ALICE, preset_files
from tiroir.core.detection import detect, load_dictionary
from tiroir.core.index import index_store
from tiroir.core.lexical import DrawerRef
from tiroir.core.store import append_log, create_store

SECOND_ID = "0b9f1e24-6d3a-4c75-8e12-a4c7d9b3f580"
BAKERY = DrawerRef("cabinet", "clients/c001")


def test_a_name_in_any_written_form_detects_the_drawer(
    data_dir: Path, store_id: str
) -> None:
    # Given
    index_store(data_dir, store_id)
    names = load_dictionary(data_dir, "cabinet", store_id)
    texts = [
        "Prépare la relance TVA pour Boulangerie Bérenger",
        "BOULANGERIE-BERENGER",
        "boulangerie bérenger",
    ]

    # When
    results = [detect(t, None, [names], {}) for t in texts]

    # Then
    for found, ambiguities in results:
        assert [d.drawer for d in found] == [BAKERY]
        assert ambiguities == ()
    assert [found[0].matched for found, _ in results] == [
        "Boulangerie Bérenger",
        "BOULANGERIE-BERENGER",
        "boulangerie bérenger",
    ]


def test_a_code_and_an_alias_detect_their_drawer(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)
    names = load_dictionary(data_dir, "cabinet", store_id)

    # When
    by_code, _ = detect("Dossier C001 à relire", None, [names], {})
    by_alias, _ = detect("Où en est Bérenger ?", None, [names], {})

    # Then
    assert [d.drawer for d in by_code] == [BAKERY]
    assert [d.drawer for d in by_alias] == [BAKERY]


def test_the_full_name_wins_over_its_alias(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)
    names = load_dictionary(data_dir, "cabinet", store_id)

    # When
    found, ambiguities = detect("Boulangerie Bérenger", None, [names], {})

    # Then
    assert [(d.drawer, d.matched) for d in found] == [(BAKERY, "Boulangerie Bérenger")]
    assert ambiguities == ()


def test_a_name_in_two_stores_is_an_ambiguity(data_dir: Path, store_id: str) -> None:
    # Given
    files = preset_files()
    files["tiroir.yaml"] = files["tiroir.yaml"].replace(
        store_id.encode(), SECOND_ID.encode()
    )
    create_store(data_dir, SECOND_ID, files, ALICE)
    index_store(data_dir, store_id)
    index_store(data_dir, SECOND_ID)
    dictionaries = [
        load_dictionary(data_dir, "cabinet", store_id),
        load_dictionary(data_dir, "annexe", SECOND_ID),
    ]

    # When
    found, ambiguities = detect("Bérenger", None, dictionaries, {})

    # Then
    assert found == ()
    assert [a.candidates for a in ambiguities] == [
        (DrawerRef("annexe", "clients/c001"), BAKERY)
    ]


def test_cwd_values_are_read_from_the_index(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)
    names = load_dictionary(data_dir, "cabinet", store_id, ["code"])

    # When
    found, _ = detect("", "/home/u/clients/C001/sub", [names], {"cabinet": ["code"]})

    # Then
    assert [(d.drawer, d.via) for d in found] == [(BAKERY, "cwd")]


def test_the_dictionary_is_cached_until_the_commit_changes(
    data_dir: Path,
    store_id: str,
) -> None:
    # Given
    index_store(data_dir, store_id)
    first = load_dictionary(data_dir, "cabinet", store_id)

    # When
    again = load_dictionary(data_dir, "cabinet", store_id)
    append_log(data_dir, store_id, "clients/c001", "Une note.", ALICE)
    index_store(data_dir, store_id)
    refreshed = load_dictionary(data_dir, "cabinet", store_id)

    # Then
    assert again is first
    assert refreshed is not first


def test_a_store_without_an_index_has_an_empty_dictionary(
    data_dir: Path, store_id: str
) -> None:
    # Given
    names = load_dictionary(data_dir, "cabinet", store_id)

    # When
    found, ambiguities = detect("Bérenger", None, [names], {})

    # Then
    assert found == () and ambiguities == ()
