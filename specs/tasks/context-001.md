---
id: context-001
title: Detect the drawers named in a text or matched by the working directory
type: feat
epic: context
depends_on: []
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

Context injection starts by finding which drawers a prompt names. ADR-008
fixes the method: exact matching of each drawer's declared names
(`detect.names`) on token boundaries, after normalisation without stemming,
the longest match winning, ambiguity reported instead of chosen, and a drawer
matched from the working directory through `detect.cwd`. The index already
holds a `names` table per store (`search-001`). This task is pure detection:
assembling and injecting context comes in `context-002`.

## Covers

- C1
- C1a
- C2
- C3 (part): detection matches declared names only, so it does not guess by
  construction; the measure on the judged negatives is `eval-003`'s

## Scope

Files this task is expected to touch:

- `src/tiroir/core/detection.py`:
  - `name_tokens(text)`: ADR-008's normalisation (NFKC, case folding,
    diacritics removed, punctuation as token boundaries, no stemming, no stop
    words), reusing `textnorm.fold`
  - a `NameDictionary` built from the names of several stores (each name
    mapped to its `DrawerRef`s), matching token n-grams in one pass, longest
    match first on overlaps
  - `detect(text, cwd, dictionaries, cwd_fields) -> (detections,
    ambiguities)`: each detection with the matched text as written in the
    input and `via` `name` or `cwd`; a name of two or more drawers, across
    the given stores, is an ambiguity listing them and detects none
  - the working-directory rule of ADR-008: slugify each folder of `cwd`
    (POSIX or Windows separators), compare with each drawer's `detect.cwd`
    field value slugified, the deepest folder wins
  - reading a store's names and `detect.cwd` values from its index with a
    read-only SQLite connection, cached per store and invalidated when the
    index's recorded commit changes
- `tests/unit/core/test_detection.py`: normalisation, n-gram matching,
  overlaps, ambiguity, cwd on both separators (pure logic, names given in
  memory); property-based with `hypothesis`: text built from words that are
  no declared name detects nothing
- `tests/integration/test_detection.py`: detection over stores created from
  the `accounting-firm` preset, reading the real index

Out of scope:

- the `MemberContext.context` call, injection, conventions, the deadline
  (`context-002`)
- the `doctor` warnings on weak names (ADR-008; `doctor` comes later)
- fuzzy or semantic detection (ADR-008: none in v1)

## Acceptance criteria

- On the preset, `Prépare la relance TVA pour Boulangerie Dupont`,
  `BOULANGERIE-DUPONT` and `boulangerie dupont` each detect the same drawer,
  with the matched text as written; a client code (`C042`) and an alias
  detect their drawer too.
- A prompt naming two clients detects both.
- A name declared by two drawers (in one store, or in two stores given
  together) is reported as one ambiguity with both refs, and neither is
  detected.
- When one name is contained in a longer one (`Dupont` and `Boulangerie
  Dupont`), the longer match wins and the shorter one is not reported
  separately.
- `cwd` `/home/u/src/api-gateway/services` detects the drawer whose
  `detect.cwd` value slugifies to `api-gateway`; `C:\src\api-gateway` does
  too; a path with no matching folder detects nothing.
- The property test finds no detection on text built only from words that
  are not names.
- Detecting on a 2,000-word prompt over a dictionary of 2,000 drawers takes
  under 20 ms in a test that measures it.
- `mise run check` passes.

## Validation

`mise run test -- tests/unit/core/test_detection.py
tests/integration/test_detection.py`, then `mise run check`.
