---
type: repo
slug: data-pipeline
name: Sluicewright
aliases: [etl, pipeline]
language: python
status: active
---
# Sluicewright

## Purpose

Nightly jobs that copy operational data to the warehouse and build the reports' tables.

## Architecture

A scheduler runs Python tasks in containers; each task writes parquet files then loads them.

## Conventions

Each job is idempotent and can be rerun for a past day. Table names start with the domain.

## Decisions

DATA-88: late events are accepted for seven days. DATA-93: personal data is hashed before loading.

## Gotchas

The night job for orders overlaps the backup window and fails with SQLSTATE 40001. Daylight saving changes shift the partitions.

## Open questions

Do we move to incremental models or keep full reloads?
