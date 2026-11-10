---
title: Code review guide
---
# Code review guide

## Size

A pull request stays under four hundred changed lines. Split it otherwise.

## What to check

Behaviour against the ticket, tests that fail without the change, error
handling on every external call, names that say what things are.

## Tone

Ask questions before asserting. Mark a remark `nit:` when it is optional.

## Merging

Squash with the ticket number in the subject, for example
`PROJ-1234: retry the upload on timeout`.
