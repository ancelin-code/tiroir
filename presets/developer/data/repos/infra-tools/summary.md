---
type: repo
slug: infra-tools
name: Rigsmith
aliases: [infra, ops tools]
language: go
status: active
---
# Rigsmith

## Purpose

Command-line tools that deploy services and check that real infrastructure matches its description.

## Architecture

A set of Go commands sharing one config loader. They call the cloud provider's API and the vault.

## Conventions

Commands are idempotent. Output is machine readable with `--json`.

## Decisions

OPS-12: secrets are referenced by vault path, never copied. OPS-15: deploys go one region at a time.

## Gotchas

The drift checker reports false alarms for autoscaled node counts. Running it from a laptop on VPN times out.

## Open questions

Should deploys move to a pull-based tool?
