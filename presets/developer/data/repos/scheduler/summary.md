---
type: repo
slug: scheduler
name: Tickwheel
aliases: [cron service, jobs]
language: python
status: active
---
# Tickwheel

## Purpose

Runs recurring jobs for all services so none needs its own cron.

## Architecture

A single active leader chosen with a lease row in Postgres; followers wait.

## Conventions

A job must finish before its next trigger or it is skipped and reported.

## Decisions

SCH-40: no catch-up runs after downtime. SCH-44: history is pruned after 60 days.

## Gotchas

Two leaders for a few seconds are possible if the database clock jumps. Jobs defined with local time ignore daylight saving.

## Open questions

Should jobs be able to depend on each other?
