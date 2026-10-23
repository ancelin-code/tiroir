"""Text normalisation and identifier tokens."""

from tiroir.core.textnorm import fold, identifier_tokens, normalize, terms


def test_fold_removes_diacritics_and_case() -> None:
    # Given
    text = "Échéance du CŒUR"

    # When
    folded = fold(text)

    # Then
    assert folded == "echeance du coeur"


def test_accented_and_plain_forms_normalise_alike() -> None:
    # Given
    plain, accented = "echeance", "échéance"

    # When
    left, right = normalize(plain, "fr"), normalize(accented, "fr")

    # Then
    assert left == right


def test_plural_and_singular_share_a_stem() -> None:
    # Given
    plural, singular = "déclarations", "déclaration"

    # When
    left, right = normalize(plural, "fr"), normalize(singular, "fr")

    # Then
    assert left == right


def test_stop_words_are_dropped() -> None:
    # Given
    text = "Le dossier de la société"

    # When
    result = terms(text, "fr")

    # Then
    assert len(result) == 2


def test_unknown_language_is_folded_but_not_stemmed() -> None:
    # Given
    text = "Déclarations"

    # When
    result = terms(text, "xx")

    # Then
    assert result == ["declarations"]


def test_digit_words_are_not_stemmed() -> None:
    # Given
    text = "factures 2026"

    # When
    result = terms(text, "fr")

    # Then
    assert result[-1] == "2026"


def test_identifier_tokens_join_digit_runs() -> None:
    # Given
    text = "SIREN 123 456 789, facture 2026-001, tel 01.02.03.04.05"

    # When
    found = identifier_tokens(text)

    # Then
    assert found == ["123456789", "2026001", "0102030405"]


def test_identifier_tokens_keep_words_with_digits() -> None:
    # Given
    text = "Client C001 et dossier A2"

    # When
    found = identifier_tokens(text)

    # Then
    assert found == ["c001", "a2"]


def test_identifier_tokens_ignore_plain_words_and_repeats() -> None:
    # Given
    text = "bonjour C001 c001"

    # When
    found = identifier_tokens(text)

    # Then
    assert found == ["c001"]
