"""Lexical search over a store's index."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tiroir.core.chunking import Kind
from tiroir.core.index import index_path, index_store, rebuild
from tiroir.core.lexical import (
    Channel,
    DrawerRef,
    Filters,
    Hit,
    Scope,
    search_lexical,
)
from tiroir.core.store import Author, append_log

EVERYWHERE = Scope(all_drawers=True)
QUERIES = [
    "echeance",
    "déclarations",
    "123456789",
    "2026-001",
    "relance",
    "tva mensuelle",
    "Bérenger",
    "zébulon quantique",
]


@pytest.fixture
def indexed(data_dir: Path, store_id: str, author: Author) -> Path:
    """The preset's store with three known entries, indexed."""
    append_log(
        data_dir,
        store_id,
        "clients/c001",
        "L'échéance de la déclaration approche. SIREN 123 456 789.",
        author,
    )
    append_log(
        data_dir,
        store_id,
        "clients/c002",
        "Facture 2026-001 à régler avant fin mois.",
        author,
    )
    append_log(
        data_dir, store_id, "clients/c002", "Relance téléphonique faite.", author
    )
    index_store(data_dir, store_id)
    return data_dir


def search(
    data_dir: Path,
    store_id: str,
    query: str,
    scope: Scope = EVERYWHERE,
    filters: Filters | None = None,
    limit: int = 10,
) -> list[Hit]:
    """Search the one store."""
    return search_lexical(data_dir, [store_id], query, scope, filters, limit)


def test_query_without_diacritics_finds_the_accented_word(
    indexed: Path, store_id: str
) -> None:
    # Given
    query = "echeance"

    # When
    hits = search(indexed, store_id, query, limit=50)

    # Then
    assert any("échéance" in hit.text for hit in hits)


def test_plural_query_finds_the_singular(indexed: Path, store_id: str) -> None:
    # Given
    query = "déclarations"

    # When
    hits = search(indexed, store_id, query, limit=50)

    # Then
    assert any("déclaration approche" in hit.text for hit in hits)


def test_siren_with_spaces_is_found_by_its_digits_and_ranked_first(
    indexed: Path, store_id: str
) -> None:
    # Given
    query = "123456789"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert hits[0].path.startswith("clients/c001/log/")
    assert "123 456 789" in hits[0].text
    assert Channel.IDENTIFIER in hits[0].channels


def test_invoice_number_is_ranked_first_among_text_matches(
    indexed: Path, store_id: str
) -> None:
    # Given
    query = "facture 2026-001"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert "2026-001" in hits[0].text
    assert hits[0].drawer == "clients/c002"


def test_invoice_number_alone_is_found_and_ranked_first(
    indexed: Path, store_id: str
) -> None:
    # Given
    query = "2026-001"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert hits[0].path.startswith("clients/c002/log/")
    assert "Facture 2026-001" in hits[0].text
    assert Channel.IDENTIFIER in hits[0].channels


def test_surname_ranks_the_matching_summary_first(indexed: Path, store_id: str) -> None:
    # Given
    query = "Bérenger"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert hits[0].drawer == "clients/c001"


def test_query_sharing_no_term_abstains(indexed: Path, store_id: str) -> None:
    # Given
    query = "zébulon quantique"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert hits == []


def test_query_of_stop_words_only_abstains(indexed: Path, store_id: str) -> None:
    # Given
    query = "le de la"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert hits == []


def test_one_matching_term_of_four_is_below_the_floor(
    indexed: Path, store_id: str
) -> None:
    # Given
    query = "relance zébulon quantique cosmique"

    # When
    hits = search(indexed, store_id, query)

    # Then
    assert hits == []


def test_hit_carries_its_provenance(indexed: Path, store_id: str) -> None:
    # Given
    query = "facture 2026-001"

    # When
    hit = search(indexed, store_id, query)[0]

    # Then
    assert hit.kind is Kind.LOG
    assert hit.path.startswith("clients/c002/log/")
    assert hit.author == "alice"
    assert hit.date == datetime.now(UTC).date()
    assert hit.store == "cabinet-exemple"
    assert Channel.LEXICAL in hit.channels


def test_no_scope_returns_shared_chunks_only(indexed: Path, store_id: str) -> None:
    # Given
    scope = Scope()

    # When
    hits = search(indexed, store_id, "tva", scope)

    # Then
    assert hits
    assert {hit.kind for hit in hits} == {Kind.SHARED}


def test_drawer_scope_returns_that_drawer_and_the_shared_space(
    indexed: Path, store_id: str
) -> None:
    # Given
    scope = Scope(drawers=(DrawerRef("cabinet-exemple", "clients/c001"),))

    # When
    hits = search(indexed, store_id, "tva", scope)

    # Then
    assert {hit.drawer for hit in hits} <= {None, "clients/c001"}
    assert {hit.drawer for hit in hits} == {None, "clients/c001"}


def test_scope_of_another_store_searches_nothing(indexed: Path, store_id: str) -> None:
    # Given
    scope = Scope(drawers=(DrawerRef("autre-cabinet", "clients/c001"),))

    # When
    hits = search(indexed, store_id, "tva", scope)

    # Then
    assert hits == []


def test_filter_by_drawer_type(indexed: Path, store_id: str) -> None:
    # Given
    filters = Filters(types=("client",))
    other = Filters(types=("autre",))

    # When
    hits = search(indexed, store_id, "tva", filters=filters)
    others = search(indexed, store_id, "tva", filters=other)

    # Then
    assert hits
    assert all(hit.drawer is not None for hit in hits)
    assert not others


def test_filter_by_kind(indexed: Path, store_id: str) -> None:
    # Given
    filters = Filters(kinds=(Kind.LOG,))

    # When
    hits = search(indexed, store_id, "relance", filters=filters)

    # Then
    assert hits
    assert {hit.kind for hit in hits} == {Kind.LOG}


def test_filter_by_field_value(indexed: Path, store_id: str) -> None:
    # Given
    everything = search(indexed, store_id, "tva", limit=50)
    filters = Filters(fields={"legal_form": "sarl"})

    # When
    hits = search(indexed, store_id, "tva", filters=filters, limit=50)

    # Then
    assert hits
    assert len(hits) < len(everything)
    assert all(hit.drawer is not None for hit in hits)


def test_filter_by_field_value_in_a_list(indexed: Path, store_id: str) -> None:
    # Given
    filters = Filters(fields={"aliases": "BB"})

    # When
    hits = search(indexed, store_id, "tva", filters=filters)

    # Then
    assert hits
    assert {hit.drawer for hit in hits} == {"clients/c001"}


def test_filter_by_date_range(indexed: Path, store_id: str) -> None:
    # Given
    old = Filters(until=date(2025, 12, 31))
    recent = Filters(since=date(2026, 1, 1))

    # When
    before = search(indexed, store_id, "tva", filters=old, limit=50)
    after = search(indexed, store_id, "tva", filters=recent, limit=50)

    # Then
    assert before
    assert all(
        hit.date is not None and hit.date <= date(2025, 12, 31) for hit in before
    )
    assert after
    assert all(hit.date is not None and hit.date >= date(2026, 1, 1) for hit in after)


def test_filter_by_store_name(indexed: Path, store_id: str) -> None:
    # Given
    filters = Filters(stores=("autre",))

    # When
    hits = search(indexed, store_id, "tva", filters=filters)

    # Then
    assert hits == []


def test_limit_caps_the_hits(indexed: Path, store_id: str) -> None:
    # Given
    limit = 2

    # When
    hits = search(indexed, store_id, "tva", limit=limit)

    # Then
    assert len(hits) == limit


def test_store_without_index_is_skipped(data_dir: Path, store_id: str) -> None:
    # Given
    assert not index_path(data_dir, store_id).exists()

    # When
    hits = search(data_dir, store_id, "tva")

    # Then
    assert hits == []


def test_rebuilt_index_gives_the_same_hits_in_the_same_order(
    indexed: Path, store_id: str
) -> None:
    # Given
    before = [search(indexed, store_id, query, limit=50) for query in QUERIES]
    index_path(indexed, store_id).unlink()

    # When
    rebuild(indexed, store_id)
    after = [search(indexed, store_id, query, limit=50) for query in QUERIES]

    # Then
    assert any(before)
    assert after == before


def test_incremental_index_gives_the_same_hits_as_a_rebuild(
    indexed: Path, store_id: str, author: Author
) -> None:
    # Given
    append_log(indexed, store_id, "clients/c001", "Dernier point sur la TVA.", author)
    index_store(indexed, store_id)
    incremental = [search(indexed, store_id, query, limit=50) for query in QUERIES]

    # When
    rebuild(indexed, store_id)
    rebuilt = [search(indexed, store_id, query, limit=50) for query in QUERIES]

    # Then
    assert rebuilt == incremental


def test_prefixed_code_ranks_its_own_chunk_first_and_not_another_prefix(
    indexed: Path, store_id: str, author: Author
) -> None:
    # Given
    append_log(indexed, store_id, "clients/c001", "Dossier D-001 transmis.", author)
    append_log(indexed, store_id, "clients/c002", "Dossier C-001 ouvert.", author)
    index_store(indexed, store_id)

    # When
    hits = search(indexed, store_id, "C-001")

    # Then
    assert "C-001" in hits[0].text
    assert Channel.IDENTIFIER in hits[0].channels
    other = [hit for hit in hits if "D-001" in hit.text]
    assert all(Channel.IDENTIFIER not in hit.channels for hit in other)


def test_number_query_finds_a_prefixed_invoice_number(
    indexed: Path, store_id: str, author: Author
) -> None:
    # Given
    append_log(indexed, store_id, "clients/c001", "Avoir FAC-2027-002 émis.", author)
    index_store(indexed, store_id)

    # When
    hits = search(indexed, store_id, "2027-002")

    # Then
    assert "FAC-2027-002" in hits[0].text
    assert Channel.IDENTIFIER in hits[0].channels


def test_garbage_index_file_is_rebuilt(indexed: Path, store_id: str) -> None:
    # Given
    fresh = [search(indexed, store_id, query, limit=50) for query in QUERIES]
    index_path(indexed, store_id).write_bytes(b"this is not a database" * 100)

    # When
    report = rebuild(indexed, store_id)
    after = [search(indexed, store_id, query, limit=50) for query in QUERIES]

    # Then
    assert report.rebuilt
    assert any(fresh)
    assert after == fresh


def test_garbage_index_file_is_replaced_by_an_index_run(
    indexed: Path, store_id: str
) -> None:
    # Given
    fresh = search(indexed, store_id, "echeance", limit=50)
    index_path(indexed, store_id).write_bytes(b"\x00garbage")

    # When
    report = index_store(indexed, store_id)

    # Then
    assert report.rebuilt
    assert search(indexed, store_id, "echeance", limit=50) == fresh


def test_search_skips_a_broken_store_and_keeps_the_good_one(
    indexed: Path, store_id: str
) -> None:
    # Given
    broken = "00000000-0000-4000-8000-000000000000"
    index_path(indexed, broken).write_bytes(b"not sqlite at all" * 50)
    expected = search(indexed, store_id, "echeance", limit=50)

    # When
    hits = search_lexical(indexed, [broken, store_id], "echeance", EVERYWHERE, limit=50)

    # Then
    assert expected
    assert hits == expected
