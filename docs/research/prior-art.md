# Prior art review

Condensed input for the tiroir requirements and decision records. Studied on
2026-10-21 from shallow clones of each repository's default branch. Figures
quoted below are the projects' own claims unless stated otherwise.

## Summary table

| Project | Source of truth | Index | Scoping | Ambient injection | Licence | Takeaway for tiroir |
|---|---|---|---|---|---|---|
| [agentcairn](https://github.com/ccf/agentcairn) (Python) | Markdown vault | DuckDB, rebuildable, outside the vault | one vault, current project boosted, cross-project labelled | Claude Code `UserPromptSubmit` + `SessionStart` | Apache-2.0 | closest architecture to the brief; borrow its contracts and hook hygiene |
| [Cairn (KalebKE)](https://github.com/KalebKE/cairn) (Python, fork of omega-memory) | SQLite | FTS5 + sqlite-vec, 4-channel RRF, gated reranker | none (one global store) | thin hook client over a socket into the MCP process | Apache-2.0 | abstention, rank fusion, eval discipline, hook latency pattern |
| [agent-memory-kit](https://github.com/awrshift/agent-memory-kit) (skills + hooks, no runtime) | Markdown in the working folder | none | `projects/<client>/` folders | Claude Code hooks only | MIT | "propose, then write"; dated lines; honest per-host capability matrix |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) (Python) | Markdown | SQLite or Postgres, FTS + FastEmbed vectors | "projects" (separate folders) | none (MCP tools) | AGPL-3.0 | already has per-type note schemas (Picoschema); multilingual embedding evidence |
| [claude-mem](https://github.com/thedotmack/claude-mem) (TS/Bun) | SQLite | FTS5 + Chroma | per project | hooks + worker service | Apache-2.0 | automatic capture; `<private>` exclusion tags; progressive disclosure |
| [agentmemory](https://github.com/rohitg00/agentmemory) (TS) | own state store | BM25, optional local MiniLM | per project | 12 hooks, 54 MCP tools, 4 local ports | Apache-2.0 | counter-example for "light": heavy runtime and tool surface |
| [Agent Memory Repo](https://github.com/AgentMemoryRepo/agentmemoryrepo) (format spec, Cognition) | Git repo of Markdown | none | free layout | `MEMORY.md` loaded at session start | spec | a lightweight interchange format a store could stay compatible with |

## Ideas worth borrowing

### Storage and index

- **Markdown canonical, index disposable** (agentcairn, Basic Memory). Keep the
  index outside the synced repository; a failed rebuild keeps the last good
  index and never touches files.
- **Reconcile on read** (agentcairn): the first query of a process brings the
  index in sync with the files, so hand edits and `git pull` need no watcher.
- **Write-through** (agentcairn): a successful write updates file and index
  under one lock, so the next search sees it.
- **Brute-force vector scan is enough at our scale** (agentcairn benchmark):
  under 2 ms at 1k chunks, about 14 ms at 10k, crossing 100 ms only near 100k
  chunks. A store with a few hundred drawers will not need an ANN index.

### Retrieval

- **Rank fusion, not score fusion** (Cairn, agentcairn): BM25 and cosine
  scores live on different scales; Reciprocal Rank Fusion avoids calibrating
  them against each other.
- **Fusion guard** (Cairn): keeping the vector channel's top hit in the final
  top 3 lifted every metric, because lexical and vector channels fail on
  different queries.
- **Abstention** (Cairn): an absolute floor on the composite score; returning
  nothing cost one question in 500 on LongMemEval recall@5.
- **The abstention threshold is model-specific** (Basic Memory): the same 0.55
  cutoff gave 75% false positives on negative queries with an English model and
  0% with a multilingual one. Changing the embedding model must re-calibrate
  the threshold, which argues for shipping the evaluation harness with v1.
- **Use a multilingual model for French** (Basic Memory): multilingual MiniLM
  beat English BGE-small on MRR and wrong-top rate, at 384 dimensions.
- **Rerankers are optional and slow on the hot path** (agentcairn forces them
  off in the prompt hook; Cairn only lets a confident reranker override).

### Injection and hooks

- **Fail open** (agentcairn): any error, timeout or empty result injects
  nothing and never blocks the prompt.
- **Trust boundary** (agentcairn): injected memories are framed as untrusted
  data, every line quoted so a note cannot break out of the quotation and
  inject instructions.
- **Latency** (agentcairn, Cairn): loading an embedding model per hook process
  costs about 0.5 to 1.5 s even when warm. Cairn reaches about 50 ms by
  running a thin hook client that talks to the already-running MCP process
  over a Unix socket (TCP loopback on Windows), falling back to a direct run.
- **Skip trivial prompts** (agentcairn): "yes", "go" and other short
  continuations do not trigger recall.
- **Progressive disclosure** (claude-mem, Cairn): inject short previews with
  identifiers; the agent fetches the full entry only if needed.

### Host reality

- **Claude Desktop / Cowork run no plugin hooks** (agent-memory-kit
  `docs/specs/cowork.md`, citing open `anthropics/claude-code` issues
  #27398, #47993, #51281). Skills and MCP tools work; ambient injection does
  not. Memory there is pull-based: the model must call a tool.
- **State degraded behaviour per host, honestly** (agent-memory-kit): a
  capability matrix, each claim labelled verified or documented-only.
- **One-click install for Claude Desktop** through MCP Bundles (`.mcpb`,
  formerly DXT). Server types are `node`, `python`, `binary` and, from
  manifest 0.4, `uv` (Claude Desktop manages Python from `pyproject.toml`).
  Node ships with Claude Desktop on macOS and Windows. To verify against
  `modelcontextprotocol/mcpb` `MANIFEST.md` before deciding.

### Writing and curation

- **Propose, then write** (agent-memory-kit): nothing durable is written
  without the user's yes; matches the brief's "humans own the synthesis".
- **Dated entries make staleness visible** (agent-memory-kit, Agent Memory
  Repo `[added: YYYY-MM-DD]`).
- **Promotion path** (agent-memory-kit): a pattern seen on three dates is
  proposed for promotion from log to summary or convention.
- **Supersede, never silently erase** (agentcairn `valid_until` /
  `superseded_by`, Cairn audit log).
- **Redaction before write** (agentcairn) and **`<private>` exclusion tags**
  (claude-mem).

### Product and process

- **Guided setup that reads first and proposes before writing**, re-runnable
  (agent-memory-kit).
- **`doctor`** that checks models, index and configuration (agentcairn, Cairn),
  and watches a retrieval-quality trend (Cairn).
- **Hermetic, reproducible evaluation** with non-self-referential judged
  probes and paired A/B on any knob (Cairn).

## What to avoid

- Global, unscoped stores (Cairn) and "boost the current project but still
  return others" (agentcairn): fine for developers, a confidentiality failure
  when drawers hold different clients' confidential data.
- Heavy runtimes: daemons with several ports, dozens of MCP tools
  (agentmemory: 54 tools, 4 ports). A large tool surface also costs context
  on every session.
- LLM-driven automatic memory evolution and contradiction resolution (Cairn,
  agentmemory) for v1: opaque, nondeterministic, and at odds with "humans own
  the synthesis".
- Cloud sync offerings bundled into the product (claude-mem, Basic Memory).

## Where tiroir is genuinely different

- Basic Memory already validates notes against per-type schemas, and
  agent-memory-kit already keeps one folder per client with a guided setup.
  No project combines a **user-declared scope model** (types, layout,
  metadata, detection, injection policy) with **isolation as a tested
  guarantee**, **schema migration** and **team sync through Git**. The
  differentiation is the combination, not any single feature.
- None of the projects targets non-developers on Claude Desktop with working
  memory; agent-memory-kit documents that path as degraded.
