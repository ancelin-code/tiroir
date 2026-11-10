---
type: repo
slug: sdk-python
name: Brambleworth Python SDK
aliases: [python sdk, brambleworth-py]
language: python
status: maintenance
---
# Brambleworth Python SDK

## Purpose

The official Python client for [[repos/api/summary]].

## Architecture

A typed client generated in part from the API description, with a hand-written retry policy.

## Conventions

Semantic versioning. Every release has a changelog entry and a migration note if needed.

## Decisions

SDKP-31: only idempotent calls are retried. SDKP-35: timeouts default to 10 seconds.

## Gotchas

The generated models drift from the API when the description is edited by hand. Python 3.8 is no longer tested.

## Open questions

Is async support worth a second client?
