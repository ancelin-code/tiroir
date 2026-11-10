---
type: repo
slug: ml-features
name: Featurebarn
aliases: [features, ml]
language: python
status: active
---
# Featurebarn

## Purpose

Computes and serves the features used by the recommendation models.

## Architecture

Batch jobs write to a store; a serving cache answers online lookups in under 10 ms.

## Conventions

Every feature has an owner, a description and a freshness limit.

## Decisions

ML-16: features are versioned and never edited in place. ML-19: training and serving use the same code.

## Gotchas

A backfill over more than 90 days exhausts the warehouse quota. The serving cache returns null, not an error, for unknown users.

## Open questions

Do we need a feature store at all for ten features?
