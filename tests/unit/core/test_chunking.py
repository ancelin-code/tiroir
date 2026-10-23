"""Cutting bodies into chunks."""

from tiroir.core.chunking import log_chunks, sections, shared_chunks, summary_chunks


def test_summary_yields_one_chunk_per_section() -> None:
    # Given
    body = "# Titre\n\n## Identité\nSARL.\n\n## Missions\nTenue.\n"

    # When
    chunks = summary_chunks(body)

    # Then
    assert [(c.section, c.text) for c in chunks] == [
        (None, "# Titre"),
        ("Identité", "SARL."),
        ("Missions", "Tenue."),
    ]


def test_empty_sections_are_dropped() -> None:
    # Given
    body = "## Vide\n\n## Plein\nTexte\n"

    # When
    chunks = sections(body)

    # Then
    assert [c.section for c in chunks] == ["Plein"]


def test_headings_inside_code_fences_do_not_split() -> None:
    # Given
    body = "## A\n```\n## pas un titre\n```\n"

    # When
    chunks = shared_chunks(body)

    # Then
    assert [c.section for c in chunks] == ["A"]


def test_level_three_headings_stay_in_their_section() -> None:
    # Given
    body = "## A\ntexte\n### Détail\nsuite\n"

    # When
    chunks = shared_chunks(body)

    # Then
    assert len(chunks) == 1
    assert "### Détail" in chunks[0].text


def test_heading_keeps_a_trailing_hash_but_drops_a_closing_run() -> None:
    # Given
    body = "## C#\nun\n## Échéances ##\ndeux\n"

    # When
    chunks = sections(body)

    # Then
    assert [c.section for c in chunks] == ["C#", "Échéances"]


def test_short_log_entry_is_one_chunk() -> None:
    # Given
    body = "Premier paragraphe.\n\nSecond paragraphe.\n"

    # When
    chunks = log_chunks(body)

    # Then
    assert [c.text for c in chunks] == ["Premier paragraphe.\n\nSecond paragraphe."]


def test_long_log_entry_splits_at_paragraphs() -> None:
    # Given
    paragraphs = [" ".join(["mot"] * 250) for _ in range(3)]
    body = "\n\n".join(paragraphs)

    # When
    chunks = log_chunks(body, max_tokens=400)

    # Then
    assert [c.text for c in chunks] == [
        paragraphs[0],
        paragraphs[1],
        paragraphs[2],
    ]


def test_paragraphs_are_grouped_up_to_the_limit() -> None:
    # Given
    paragraphs = [" ".join(["mot"] * 150) for _ in range(3)]
    body = "\n\n".join(paragraphs)

    # When
    chunks = log_chunks(body, max_tokens=400)

    # Then
    assert [c.text for c in chunks] == [
        "\n\n".join(paragraphs[:2]),
        paragraphs[2],
    ]


def test_one_overlong_paragraph_stays_whole() -> None:
    # Given
    body = " ".join(["mot"] * 900)

    # When
    chunks = log_chunks(body)

    # Then
    assert len(chunks) == 1


def test_empty_log_body_has_no_chunk() -> None:
    # Given
    body = "\n \n"

    # When
    chunks = log_chunks(body)

    # Then
    assert chunks == []
