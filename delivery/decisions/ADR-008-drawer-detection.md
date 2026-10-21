# ADR-008: Detect drawers by exact matching of declared names, and by working directory

**Status:** proposed
**Date:** 2026-10-21

## Context

Detection runs on every prompt within 300 ms (P1), must find every drawer that
is explicitly named (C1), report ambiguity instead of choosing (C2) and never
guess (C3). It decides what gets injected, so a false detection is a scope
leak into the conversation.

## Decision

- **Names:** for each drawer, the values of the fields its type lists under
  `detect.names` in the schema (an identifier, a name, a list of aliases).
- **Normalisation:** the text normalisation of ADR-007 without stemming or
  stop-word removal: NFKC, case folding, diacritics removed, punctuation
  turned into token boundaries. `Boulangerie Dupont`, `boulangerie dupont` and
  `BOULANGERIE-DUPONT` are the same name.
- **Matching:** a name matches when its token sequence appears in the
  prompt's token sequence on token boundaries. Implemented as a dictionary of
  token n-grams built from the names table of the index (ADR-005); the longest
  match wins when matches overlap.
- **Ambiguity:** a matched name mapping to more than one drawer, across all
  stores in use, is reported as ambiguous with the candidate drawers, and
  nothing is injected for it (C2).
- **Working directory (C1a):** a drawer type may name a field under
  `detect.cwd`; the drawer whose field value equals the folder name of the
  working directory's repository root, or its `origin` remote URL, is
  detected.
- **Weak names:** `doctor` warns about names shorter than three characters,
  made only of digits shorter than five, or equal to a stop word of the store
  language; they are still matched, the user decides.
- **No semantic or fuzzy detection** in v1.

## Alternatives considered

- **Embedding similarity between prompt and drawers** - needs the model in the
  hook (over a second per process, ADR-009) and guesses by construction,
  against C3.
- **Fuzzy matching (edit distance)** - catches typos but turns `Durand` into
  `Durant`, a different client; a wrong injection costs more than a missed one.
- **Asking the model to name the drawers** - costs a model call per prompt
  and is not deterministic or testable.

## Consequences

Detection is deterministic, explainable (each match reports the text that
matched) and testable with zero false detections on negatives by
construction, apart from names the user declared. A typo or an undeclared
nickname is missed: the user adds an alias. Common-word names (a client
called "Orange") will match ordinary text; `doctor` flags them and the user
chooses a more specific alias.
