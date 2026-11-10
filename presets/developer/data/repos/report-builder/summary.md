---
type: repo
slug: report-builder
name: Tallyhouse
aliases: [reports, report builder]
language: java
status: maintenance
---
# Tallyhouse

## Purpose

Lets managers define reports and receive them by e-mail on a schedule.

## Architecture

A Java service that runs queries on the warehouse and renders PDFs. Schedules are rows in Postgres.

## Conventions

Reports are defined in YAML and reviewed like code.

## Decisions

REP-33: queries are read-only and limited to five minutes. REP-37: PDFs are kept for 30 days.

## Gotchas

Large reports run out of memory above 200,000 rows and the pod is killed. Fonts are missing in the slim container image.

## Open questions

Replace PDFs with live dashboards?
