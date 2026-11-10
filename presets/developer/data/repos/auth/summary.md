---
type: repo
slug: auth
name: Keyhollow
aliases: [auth lib, keyhollow]
language: python
status: maintenance
---
# Keyhollow

## Purpose

A small shared library that parses and validates access tokens for Python services.

## Architecture

Pure Python, no network calls except fetching the signing keys, which are cached for ten minutes.

## Conventions

Public functions are typed and documented. Breaking changes need a deprecation release first.

## Decisions

AUTH-19: keys are fetched lazily. AUTH-23: clock skew tolerance is 30 seconds.

## Gotchas

A token signed with an unknown key id raises a generic error, not a missing-key error. Python 3.9 support ends in 2026.

## Open questions

Merge into [[repos/auth-service/summary]] or keep it separate?
