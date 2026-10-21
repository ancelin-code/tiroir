# ADR-002: Build tiroir in Rust and distribute it as one signed binary per platform

**Status:** proposed
**Date:** 2026-10-21

## Context

Every component (core, MCP server, CLI, adapters) shares one runtime, and the
runtime decides how a non-developer installs tiroir in Claude Desktop without a
terminal (U4), how it runs on macOS, Windows and Linux (D1), how fast the
per-prompt hook starts (P1) and how light the install is (brief: "simple,
light, efficient"). A Python build was first considered and measured
(see Alternatives); the project owner chose Rust on 2026-10-21.

## Decision

- **Language:** Rust, stable toolchain, edition 2024, one Cargo workspace
  (crate layout in ADR-013). The crate name `tiroir` is free on crates.io as of
  2026-10-21.
- **One binary, `tiroir`,** containing the CLI, the MCP server (`tiroir mcp`)
  and the hook entry points (`tiroir hook …`), for six targets:
  `aarch64-apple-darwin`, `x86_64-apple-darwin` (shipped together as a
  universal macOS binary), `x86_64-pc-windows-msvc`,
  `aarch64-pc-windows-msvc`, `x86_64-unknown-linux-gnu`,
  `aarch64-unknown-linux-gnu`.
- **Native code linked in:** SQLite (bundled by `rusqlite`, with FTS5),
  libgit2 and libssh2 (vendored by `git2`), and ONNX Runtime from `ort`'s
  prebuilt libraries, statically where `ort` provides a static build for the
  target, otherwise shipped beside the binary. No runtime, interpreter or
  system library beyond the operating system's own is required.
- **Main dependencies:** `rmcp` (MCP, with elicitation), `fastembed` on `ort`
  (embeddings, ADR-006), `rusqlite` (index, ADR-005), `rust-stemmers`
  (Snowball stemming, ADR-007), `aho-corasick` (detection, ADR-008), `git2`
  and `keyring` (Git and credentials, ADR-010), `toml_edit` (schema
  round-trip, ADR-003), `saphyr` (frontmatter parsing), `directories`,
  `fs4` (file locks), `clap`, `serde`, `tokio`.
- **Releases:** built in GitHub Actions for every target, published on GitHub
  Releases with checksums and build provenance attestations. macOS binaries
  are signed with a Developer ID and notarized; Windows binaries are
  Authenticode-signed. An unsigned binary is never published as a release.
- **Installation:**
  - Claude Desktop: an MCP Bundle (`.mcpb`) of server type `binary`, one per
    operating system (macOS universal; Windows with both architectures).
    Installing it is a double-click.
  - Claude Code and terminal users: an install script per platform
    (`install.sh`, `install.ps1`) that downloads the release, checks its
    checksum and places `tiroir` in the user's binary folder without
    administrator rights; `cargo install tiroir` for Rust users. The Claude
    Code plugin runs that installed executable (ADR-013).
- **Development:** `cargo` with `clippy` and `rustfmt`, `cargo test` and
  `cargo nextest`, `cargo deny` for licences and advisories (ADR-001), CI on
  macOS, Windows and Linux.

## Alternatives considered

- **Python 3.12 distributed through `uv`** - the first candidate. Measured on
  2026-10-21: Python with light imports starts in 30 ms, but the Desktop path
  depends on the recent `uv` bundle type and downloads an interpreter plus
  some 300 MB of dependencies on first run, and `uvx` adds 130 to 210 ms per
  launch. Its strengths, easier review for the project owner and faster
  iteration on retrieval tuning, did not outweigh a lighter and simpler
  install for non-developers.
- **TypeScript on Node** - Node ships inside Claude Desktop, but local
  embeddings, stemming and Git libraries are weaker, and Node is not present
  for Claude Code users by default.
- **Go** - single binaries and a pure Go Git library with push (go-git), but
  ONNX Runtime and the Hugging Face tokenizers are only reachable through cgo,
  which gives up Go's simple cross-compilation, and there is no maintained
  equivalent of fastembed.
- **A Rust core with Python bindings (PyO3)** - two toolchains to build and
  two languages to review, for no gain over either pure option.

## Consequences

The install is one file of a few tens of megabytes plus the model download,
starts in milliseconds and needs nothing else on the machine. In exchange:

- signing costs money and setup: an Apple Developer membership with
  notarization in CI, and a Windows code-signing certificate or service;
- the CI build matrix is larger, and ONNX Runtime linking per target is the
  part most likely to break; it is proven first, before feature work;
- compile times and review effort are higher than in Python, and retrieval
  tuning iterates more slowly, which the evaluation harness (V1) mitigates by
  making every change measurable;
- the latency and memory figures in ADR-006 and ADR-009 were measured with the
  Python stack on the same ONNX models; they are re-measured with the Rust
  build in the first milestone, and the records updated if they move.
