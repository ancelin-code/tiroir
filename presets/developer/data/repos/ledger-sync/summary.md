---
type: repo
slug: ledger-sync
name: Counting House Sync
aliases: [ledger, sync]
language: java
status: active
---
# Counting House Sync

## Purpose

Exports billing events to the accounting system and reconciles the totals every night.

## Architecture

A batch application reading from [[repos/billing-service/summary]] and writing files to a drop folder.

## Conventions

Every export file has a checksum line. A mismatch stops the run.

## Decisions

LED-7: one file per day and legal entity. LED-12: rounding happens only at the export.

## Gotchas

The accounting system rejects files over 20 MB with E5120. Entities with a trailing space in the name fail the mapping.

## Open questions

Switch from files to the accounting system's new API?
