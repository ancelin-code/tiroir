---
type: repo
slug: image-resizer
name: Pixelmill
aliases: [resizer, thumbnails]
language: rust
status: active
---
# Pixelmill

## Purpose

Produces thumbnails and web-sized variants of uploaded product photos.

## Architecture

A Rust HTTP service with an on-disk cache in front of object storage. Sizes come from a fixed ladder.

## Conventions

Only sizes on the ladder are served; anything else returns 400.

## Decisions

IMG-5: output is WebP with a JPEG fallback. IMG-8: originals are never modified.

## Gotchas

Progressive JPEGs from one camera brand fail to decode and return E2207. The cache is not shared between pods.

## Open questions

Do we add AVIF output?
