---
type: repo
slug: api-gateway
name: Brambleworth Gateway
aliases: [gateway, edge]
language: go
status: active
---
# Brambleworth Gateway

## Purpose

The edge proxy in front of every Brambleworth service. It terminates TLS, checks tokens and applies rate limits.

## Architecture

A single Go binary with a hot-reloaded route table in YAML. It forwards to [[repos/api/summary]] and [[repos/auth-service/summary]].

## Conventions

Config changes need a dry run with `gateway check`. Every route has an owner field.

## Decisions

GW-212: limits are per token, not per IP. GW-240: no request body is ever logged.

## Gotchas

A route table with a duplicate prefix loads without error and silently shadows the second route. The limiter resets on pod restart.

## Open questions

Is it worth moving the limiter state to Redis to survive restarts?
