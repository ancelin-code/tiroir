---
type: repo
slug: search-indexer
name: Burrowfind Indexer
aliases: [indexer, burrowfind]
language: rust
status: active
---
# Burrowfind Indexer

## Purpose

Builds and updates the search index of products from change events.

## Architecture

A Rust binary reading deltas from a stream and writing segments to object storage; a merger compacts them hourly.

## Conventions

Benchmarks guard every change to the tokenizer. No `unwrap` outside tests.

## Decisions

IDX-30: the index is rebuilt from scratch every Sunday. IDX-34: stemming is language specific.

## Gotchas

The merger needs twice the disk of the biggest segment. A reindex while a deploy is running leaves duplicates.

## Open questions

Is vector search worth the cost for our catalogue size?
