---
type: repo
slug: web-app
name: Brambleworth Web
aliases: [storefront, web]
language: typescript
status: active
---
# Brambleworth Web

## Purpose

The customer-facing storefront, a single-page application with server rendering for product pages.

## Architecture

A React app built with Vite and rendered by a small Node server. It talks only to [[repos/api-gateway/summary]].

## Conventions

Components live in `src/ui`, one folder each, with a story. Snapshot tests are forbidden.

## Decisions

WEB-77: the cart lives on the server, not in local storage. WEB-91: the checkout is one page.

## Gotchas

The product grid breaks on Safari 16 when the image ratio is missing. Feature flags come from [[repos/feature-flags/summary]] at build time.

## Open questions

Do we still need the Internet Explorer banner? Traffic from it is under 0.1%.
