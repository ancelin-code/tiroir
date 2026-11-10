---
title: Developer conventions
---
# Developer conventions

## Writing

Write in English, in the present tense, in short sentences. A log entry has two
parts: **What** and **Next**.

## Identifiers

Tickets are written `PROJ-1234`, issues and pull requests `#482`, versions
`v2.14.3`. Repository slugs are lowercase with hyphens, such as `api-gateway`.

## Secrets

Never copy a token, a password or a private key into the memory. Name the
vault entry instead. Hosts are written on `example.com`.

## Branches

Work happens on `feature/<ticket>-<topic>`, merged by squash into `main`.
