---
type: repo
slug: sdk-js
name: Brambleworth JavaScript SDK
aliases: [js sdk, brambleworth-js]
language: typescript
status: maintenance
---
# Brambleworth JavaScript SDK

## Purpose

The official JavaScript and TypeScript client for [[repos/api/summary]].

## Architecture

A small package with no dependencies that works in browsers and Node. Types are generated.

## Conventions

Bundle size is checked in CI and must stay under 12 KB.

## Decisions

SDKJ-12: ESM only from v3. SDKJ-14: errors are classes with a code field.

## Gotchas

Older bundlers fail to read the package exports map. The pagination helper loops forever if the server returns the same cursor.

## Open questions

Should the SDK hide cursors completely?
