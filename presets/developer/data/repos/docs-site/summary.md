---
type: repo
slug: docs-site
name: Brambleworth Docs
aliases: [docs, handbook]
language: typescript
status: maintenance
---
# Brambleworth Docs

## Purpose

The public documentation for partners using the API.

## Architecture

A static site generated from Markdown, published to a bucket behind a CDN.

## Conventions

One page per endpoint, generated from the API description in [[repos/api/summary]].

## Decisions

DOC-21: examples use curl first. DOC-26: no screenshots of the console.

## Gotchas

The link checker times out on slow partner sites and fails the build. The CDN keeps old pages for an hour.

## Open questions

Do we version the documentation per API release?
