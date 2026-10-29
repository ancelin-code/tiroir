# Changelog

All notable changes to tiroir are recorded here. Set the date on a release's
heading when tagging it.

## [Unreleased]

## [0.1.0] - 2026-10-29

First release: the skeleton milestone, working from end to end on a VPS.

- A store is a bare Git repository of Markdown drawers, validated against its
  schema. `tiroir admin` creates one from a preset; the `accounting-firm`
  preset ships with a synthetic dataset.
- A server process with its SQLite database and a first administrator. Members
  sign in, and the server acts as the OAuth authorization server for
  connectors.
- A member-scoped core API, and an MCP endpoint with the `tiroir_search`,
  `tiroir_read`, `tiroir_write` (including `log`) and `tiroir_status` tools.
- Keyword search over the stores, indexed with SQLite FTS5.
- A container image for `linux/amd64` and `linux/arm64`, published on
  `ghcr.io/ancelin-code/tiroir`, and a Compose stack behind Caddy with
  automatic HTTPS.
- An installation guide for a VPS and a guide to connect Claude Desktop. The
  exit check ran on an Oracle Cloud ARM VPS and held.

[Unreleased]: https://github.com/ancelin-code/tiroir/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ancelin-code/tiroir/releases/tag/v0.1.0
