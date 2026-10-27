"""The pure helpers of lexical search: FTS5 phrases and SQL conditions."""

from datetime import date

from tiroir.core.chunking import Kind
from tiroir.core.lexical import Filters, Scope, _quoted, _where


def test_quoted_joins_the_words_as_or_phrases() -> None:
    # Given
    words = ["tva", "echeance"]

    # When
    result = _quoted(words)

    # Then
    assert result == '"tva" OR "echeance"'


def test_quoted_escapes_double_quotes() -> None:
    # Given
    words = ['a"b']

    # When
    result = _quoted(words)

    # Then
    assert result == '"a""b"'


def test_where_without_scope_limits_to_shared_chunks() -> None:
    # Given
    scope, filters = Scope(), Filters()

    # When
    sql, params = _where(scope, filters, [])

    # Then
    assert sql == " AND (f.kind = 'shared' OR f.drawer IN ())"
    assert params == []


def test_where_with_all_drawers_and_no_filter_has_no_condition() -> None:
    # Given
    scope, filters = Scope(all_drawers=True), Filters()

    # When
    sql, params = _where(scope, filters, [])

    # Then
    assert (sql, params) == ("", [])


def test_where_lists_the_scoped_drawers() -> None:
    # Given
    scope, filters = Scope(), Filters()

    # When
    sql, params = _where(scope, filters, ["clients/c001", "clients/c002"])

    # Then
    assert "f.drawer IN (?, ?)" in sql
    assert params == ["clients/c001", "clients/c002"]


def test_where_adds_one_condition_per_filter_in_order() -> None:
    # Given
    scope = Scope(all_drawers=True)
    filters = Filters(
        types=("client",),
        kinds=(Kind.LOG,),
        fields={"Name": "Élan"},
        since=date(2026, 1, 1),
        until=date(2026, 2, 1),
    )

    # When
    sql, params = _where(scope, filters, [])

    # Then
    assert sql.startswith(" AND f.drawer_type IN (?) AND f.kind IN (?) AND EXISTS")
    assert sql.endswith(" AND c.date >= ? AND c.date <= ?")
    assert params == [
        "client",
        "log",
        "Name",
        "elan",
        "2026-01-01",
        "2026-02-01",
    ]
