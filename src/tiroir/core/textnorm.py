"""Text normalisation for the lexical index and its queries (ADR-007).

The same functions run on indexed text and on queries: NFKC, case folding,
diacritics removed, the language's stop words dropped, Snowball stemming
(`PyStemmer`). Identifier tokens are kept apart, unstemmed and joined.
"""

import re
import threading
import unicodedata
from functools import cache

import Stemmer  # pyrefly: ignore[missing-import]  (a binary module, no stubs)

# Bump when the output of this module changes, so existing indexes rebuild.
VERSION = 2

_WORD = re.compile(r"\w+")
_DIGIT_RUN = re.compile(r"\d+(?:[ .\-]\d+)+")
_COMPOUND = re.compile(r"[^\W_]+(?:[.\-][^\W_]+)+")
_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae"})

# Snowball algorithm per store language code; other languages are not stemmed.
_ALGORITHMS = {
    "en": "english",
    "fr": "french",
    "de": "german",
    "es": "spanish",
    "it": "italian",
    "pt": "portuguese",
    "nl": "dutch",
}

_STOP_WORDS_FR = """
au aux avec ce ces cet cette dans de des du elle en et eux il ils je la le les
leur lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que
qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l a m n s
t y ete etre est sont sera soit etait ont avoir ai as avons avez ete fait si
"""
_STOP_WORDS_EN = """
a an and are as at be but by for if in into is it no not of on or such that the
their then there these they this to was will with
"""


def fold(text: str) -> str:
    """NFKC, case folded, with diacritics removed (`Échéance` -> `echeance`)."""
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_LIGATURES)
    decomposed = unicodedata.normalize("NFKD", folded)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@cache
def _stop_words(language: str) -> frozenset[str]:
    """The folded stop words of a language; none for an unknown one."""
    words = {"fr": _STOP_WORDS_FR, "en": _STOP_WORDS_EN}.get(language, "")
    return frozenset(fold(word) for word in words.split())


_local = threading.local()


def _stemmer(language: str) -> Stemmer.Stemmer | None:
    """This thread's stemmer for the language, `None` when it has no algorithm."""
    algorithm = _ALGORITHMS.get(language)
    if algorithm is None:
        return None
    stemmers: dict[str, Stemmer.Stemmer] = _local.__dict__.setdefault("stemmers", {})
    if algorithm not in stemmers:
        stemmers[algorithm] = Stemmer.Stemmer(algorithm)
    return stemmers[algorithm]


def terms(text: str, language: str) -> list[str]:
    """The content terms of `text`: folded words, stop words dropped, stemmed.

    Words holding a digit are kept as they are. Order and repeats are kept.
    """
    stop = _stop_words(language)
    stemmer = _stemmer(language)
    result: list[str] = []
    for word in _WORD.findall(fold(text)):
        if word in stop:
            continue
        if stemmer is not None and not any(c.isdigit() for c in word):
            word = stemmer.stemWord(word)
        result.append(word)
    return result


def normalize(text: str, language: str) -> str:
    """The terms of `text` joined by spaces: what the FTS `text` column holds."""
    return " ".join(terms(text, language))


def _joined_codes(folded: str) -> tuple[list[str], str]:
    """The joined codes of folded text and the text with them blanked out.

    A code is letters and digits joined by dashes or dots, holding both
    (`fac-2026-001` gives `fac2026001`).
    """
    codes: list[str] = []

    def take(match: re.Match[str]) -> str:
        token = match.group()
        if any(c.isdigit() for c in token) and any(c.isalpha() for c in token):
            codes.append(re.sub(r"[.\-]", "", token))
            return " "
        return token

    return codes, _COMPOUND.sub(take, folded)


def identifier_tokens(text: str, *, query: bool = False) -> list[str]:
    """The identifier tokens of `text`, unstemmed, without repeats.

    Runs of digits split by spaces, dots or dashes are joined (`123 456 789`
    gives `123456789`, `2026-001` gives `2026001`); any other word holding a
    digit is kept as it is (`c001`). A code mixing letters and digits joined
    by dashes or dots gives its joined form (`FAC-2026-001` gives
    `fac2026001`) and, when indexing, also its digit run (`2026001`), so a
    query for the number alone finds it. With `query`, only the joined form
    is returned: `C-001` must not match `D-001` through the shared `001`.
    """
    folded = fold(text)
    codes, blanked = _joined_codes(folded)
    source = blanked if query else folded
    found = codes + [re.sub(r"\D", "", run) for run in _DIGIT_RUN.findall(source)]
    rest = _DIGIT_RUN.sub(" ", source)
    found += [w for w in _WORD.findall(rest) if any(c.isdigit() for c in w)]
    return list(dict.fromkeys(found))
