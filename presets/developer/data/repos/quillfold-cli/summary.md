---
type: repo
slug: quillfold-cli
name: Quillfold CLI
aliases: [quillfold, qf]
language: rust
status: active
---
# Quillfold CLI

## Purpose

A command-line tool that formats and lints configuration files across the other repositories.

## Architecture

A single Rust binary with plugins loaded from a folder. Config is read from `quillfold.toml`.

## Conventions

Every rule has a fixture folder with input and expected output.

## Decisions

QF-9: plugins are separate binaries over stdin. QF-14: exit code 2 means a lint failure.

## Gotchas

Windows paths with spaces break the plugin loader. The formatter changes line endings unless told not to.

## Open questions

Should the plugin protocol be versioned now?
