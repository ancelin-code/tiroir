---
type: repo
slug: auth-service
name: Brambleworth Identity
aliases: [identity, login service]
language: go
status: active
---
# Brambleworth Identity

## Purpose

Handles sign-in, sessions and token refresh for every Brambleworth client.

## Architecture

A Go service with Postgres for accounts and Redis for refresh tokens. Keys rotate monthly.

## Conventions

Every endpoint has a rate limit test. Passwords are never logged, even hashed.

## Decisions

ID-64: refresh tokens rotate on use. ID-71: sessions last 14 days of inactivity.

## Gotchas

Key rotation briefly serves two key sets; clients that cache for more than ten minutes fail with E4031. Login slows down when the hash cost is raised.

## Open questions

Do we add passkeys this year?
