---
type: repo
slug: api
name: Brambleworth API
aliases: [brambleworth, core api]
language: python
status: active
---
# Brambleworth API

## Purpose

The public REST service behind the Brambleworth storefront. Customers, partners and the mobile apps all call it.

## Architecture

A FastAPI-style application on three pods, backed by Postgres 15 and a Redis cache. Requests reach it through [[repos/api-gateway/summary]].

## Conventions

Tests run with pytest and must stay under four minutes. Migrations are reviewed by a second person.

## Decisions

PROJ-1180: pagination is cursor-based, never offset. PROJ-1302: money is stored as integer cents.

## Gotchas

The pricing module caches for 60 seconds, so a price change looks stale for a minute. Local tests need Redis on port 6380.

## Open questions

Should v3 drop the legacy XML export? Nobody has used it since March 2026.
