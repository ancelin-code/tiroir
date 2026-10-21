# tiroir — Product Brief

> **tiroir** (French for *drawer*): configurable, scoped memory for AI agents.
>
> This brief describes **what** we are building and **why**, the principles and the hard constraints. It deliberately leaves most **how** decisions open. The requirements live in [`delivery/prd.md`](../delivery/prd.md); every significant design decision is recorded as a decision record (context → options → decision → consequences).

## 1. Vision

Give any AI agent a memory organized the way its user actually works.

A developer thinks in repos and services. An accountant thinks in client files. A consultant thinks in engagements, a researcher in projects and papers. Existing agent memory tools hard-code one organization, usually "coding projects". tiroir makes **the organization of memory a configuration**: the user declares their *drawers* (scopes), and tiroir handles storage, indexing, retrieval, context injection and sync.

**Simple, light, efficient, customizable.**

## 2. Problem

- Agents start every session from scratch. Users waste time re-explaining context.
- Built-in memory files (CLAUDE.md and the like) are flat, grow stale and do not separate contexts that must not mix.
- Existing memory tools are either opaque (vector blobs you cannot read), cloud-hosted (unacceptable for confidential data), or designed only for developers and their repos.
- Professionals bound by confidentiality (accountants, lawyers, consultants) need **strict isolation between scopes**. Mixing two clients' contexts is a serious failure, not a minor inaccuracy.

## 3. Prior art and positioning

The agent-memory space is crowded. The review of the projects below is in [`docs/research/prior-art.md`](research/prior-art.md):

- **agentcairn**: local-first; a Markdown (Obsidian) vault as source of truth; a rebuildable index; installers for many hosts.
- **Cairn (KalebKE)**: SQLite with FTS5 and sqlite-vec, hybrid retrieval, ambient injection via hooks. It **abstains** when nothing clears a score threshold — adopted.
- **agent-memory-kit**: plain Markdown in the repo, re-runnable guided setup, "propose before writing".
- **Basic Memory**: Markdown with a semantic graph and per-type note schemas, MCP, a Teams offering.
- **claude-mem**, **agentmemory** and others: automatic capture and compression of session activity.
- **Agent Memory Repo** (Cognition): a lightweight format for a Git repository of agent memory.

**tiroir's differentiation, which must be preserved by every design decision.** No single item is unique; the combination is:

1. **User-defined memory schema.** Scope types, folder layout, metadata, templates and injection rules are configuration, not code.
2. **Strict scope isolation** as a tested guarantee.
3. **Guided initialization** through an agent skill that interviews the user and designs the schema with them, plus a **migration** path when needs evolve.
4. **Usable by non-developers** (via Claude Desktop today), and not only by developers in a terminal.
5. **Team-ready through Git**: shared memory, history and access control delegated to the Git host, with Git itself fully managed by tiroir.

## 4. Principles

1. **Plain files are the truth.** Memory is human-readable Markdown in a Git repository, readable without tiroir. Every index is derived and rebuildable.
2. **tiroir owns the history.** tiroir manages Git autonomously and transparently; users never touch Git. It is the only writer to a store's shared history: files edited outside tiroir are detected and shared only once confirmed through tiroir, and never if they break an invariant.
3. **Local and private by default.** No telemetry, no third-party APIs. Embeddings are computed on infrastructure the user controls. The only network traffic is to the user's Git remote and the one-time model download.
4. **Isolation over recall.** When drawers are active, retrieval stays inside them. Searching across drawers is explicit.
5. **Abstain rather than mislead.** Injecting nothing is better than injecting a plausible but wrong memory.
6. **Humans own the synthesis.** Raw entries are append-only. Rewriting a summary requires user confirmation. The only deletion is an explicit, confirmed purge.
7. **Configuration over code**, with sensible defaults and presets so that the zero-config path still works.
8. **Harness-agnostic by design, Claude-first in delivery.** The core never depends on a specific agent host.

## 5. Core concepts

The metaphor is kept as the product vocabulary.

| Concept | Meaning |
|---|---|
| **Store** | A Git repository holding one memory (an organization's, a team's, or one person's). |
| **Drawer type** (scope type) | A user-declared kind of scope: `client`, `project`, `repo`, `engagement`… with its metadata schema, templates and detection rules. |
| **Drawer** (scope) | One instance: client C042, the repo `api-gateway`… |
| **Shared space** | Store-level knowledge that does not belong to one drawer: procedures, conventions, templates, preferences. |
| **Entry kinds** | A *summary* (curated, rewritable with confirmation) and a *log* (append-only, dated). Further kinds are deferred. |
| **Schema** | The configuration file declaring drawer types, layout, metadata, templates, detection, injection policy and language. |
| **Preset** | A ready-made schema for a common use case (developer, accounting firm, consulting…). |
| **Adapter** | The thin integration layer for one agent host (hooks, install, config wiring). |

## 6. Target users

- **Developer (solo)**: memory per repo or project, mostly in Claude Code.
- **Professional (non-developer)**: confidential, scope-per-client memory, starting in Claude Desktop on macOS or Windows, possibly moving to Claude Code later.
- **Small team**: the same store shared by several people through a private Git host.

## 7. Functional requirements

The detailed, checkable requirements are in [`delivery/prd.md`](../delivery/prd.md). In short:

**Must have (v1)**

- A declarative **schema** for drawer types, layout, metadata (with validation), templates, detection rules, injection policy and language.
- An **init skill**: an agent-guided interview that proposes a schema, generates config, templates and conventions, validates them, and can be safely re-run.
- **Schema migration**: evolve the schema (add a field, rename a type, change the layout) without losing data, with a dry run.
- **Presets**: at least `developer` and `accounting-firm`, with synthetic examples only.
- **Hybrid search**: lexical search (exact identifiers, numbers, proper nouns) and semantic search with **local** embeddings, plus metadata filters. Drawer-scoped by default when drawers are active.
- **Context**: detect the drawers explicitly named in a prompt (within a strict latency budget; several named drawers are all injected, an ambiguous name injects nothing) and inject their summaries; abstain below a confidence threshold. Nothing is loaded at session start: a memory skill, whose description is generated from the schema, tells the agent when to use tiroir, and the store's conventions load on first use in a session. On hosts without hooks (Claude Desktop) the skill is the trigger and context comes on demand through MCP.
- **Write operations for agents**: append a log entry, propose a summary update (as a diff), apply it after confirmation, create a drawer from its template.
- **Erasure**: purge a drawer from the files, the index and the whole Git history, locally and on the remote, without any other clone being able to bring it back.
- **Autonomous sync** across machines through Git, with conflict handling that never silently loses data, and no Git knowledge required from the user.
- **Memory language** as a setting: it drives templates, conventions, the language the agent writes in, and lexical-search behaviour (diacritics, stemming).
- An **MCP server** usable from Claude Desktop and Claude Code.
- A **Claude Code adapter** (hooks and one-command install).
- A **CLI** for init, indexing, search, validation (`doctor`), sync, migration, purge and install.
- An **evaluation harness** on synthetic datasets (recall@k, MRR, abstention false positives, comparing lexical, semantic and hybrid) shipped in the repo, so users can evaluate and calibrate their own configuration. Promoted from Should because the abstention threshold must be calibrated per embedding model.

**Should have**

- Clear onboarding and offboarding for team members.
- Refusing to write recognised credentials.
- Compatibility with the Agent Memory Repo format.

**Later**

- An optional **self-hosted server mode** (see §9), together with **server-side enforcement** of the invariants by the Git remote.

**Out of scope for v1**

Automatic capture or compression of whole sessions, document ingestion (PDF, email, exports), a custom web UI, fine-grained per-drawer permissions (the Git host handles access per store), adapters for hosts other than Claude, encryption at rest (left to disk encryption), and any hosted or SaaS offering.

## 8. Non-functional requirements

- **Privacy**: zero egress beyond the Git remote and the model download. No client content in logs, commit messages or error output.
- **Lightweight**: easy to install, minimal dependencies, runs on an ordinary laptop CPU. Performance budgets are set in the PRD (prompt-hook latency, search latency, indexing throughput, memory).
- **Cross-platform**: macOS and Windows for Claude Desktop and Claude Code; Linux for Claude Code and servers.
- **Non-developer friendly**: the setup path for Claude Desktop users must not require a terminal beyond copy-pasting documented commands, or better.
- **Documentation and examples** good enough to adopt tiroir without reading the code.
- **Open source** under Apache-2.0.

## 9. Architecture

**v1 is local-first**: each machine clones the store, builds its own index and runs a local MCP server. Simplest, offline-capable, no server to maintain.

The design must not preclude, for a later release:

- **Self-hosted server mode**: a `docker compose` stack on a VPS (Git host such as Forgejo, tiroir server, database), exposing a remote MCP server with authentication. One index, easier for teams, but with an operational burden (TLS, auth, backups, updates), and remote MCP connectors in Claude are reached from Anthropic's infrastructure.
- **Hybrid**: Git stays the source of truth, while the server indexes on push, serves search and enforces the invariants on push.

**Git remote**: any remote over SSH or HTTPS. The documentation recommends a self-hosted Forgejo for confidential data and covers one hosted provider.

Open technical questions, each settled by a decision record: runtime (Python preferred); storage and index technology; embedding model(s) and how users switch between them; chunking per entry kind; fusion and ranking strategy, with identifier boosting and an abstention threshold; drawer detection method; how tiroir runs Git and holds its credential; how the adapter abstraction is shaped; packaging and distribution (including Claude Desktop bundles).

## 10. Harness-agnostic roadmap

Layer the system so that only the outermost layer is host-specific:

1. **Core library and CLI**: no host dependency.
2. **MCP server**: portable to any MCP-capable host.
3. **Skills**: init, migration, memory hygiene, using a portable skill format where possible.
4. **Adapters**: hooks and install per host. Only Claude Code ships in v1, but the adapter interface is designed now, and a second adapter should be cheap to add.

## 11. Design test: a small professional practice

A running design test for every decision, embodied by the `accounting-firm` preset:

- the owner works in Claude Desktop on macOS or Windows and may move to Claude Code; collaborators join later;
- one drawer per client, holding a structured summary (legal form, tax and VAT regime, fiscal year end, engagements, contacts, points of attention, deadlines) and a dated log;
- shared space for procedures, templates, a fiscal calendar and writing preferences;
- confidential data, a private Git host, local embeddings, a right to erasure;
- French as the memory language.

Real deployments keep their stores (data and configuration) in their own private repositories. The public tiroir repository only ships presets with synthetic data.

## 12. Success criteria

- A developer goes from install to useful memory in under 10 minutes using a preset.
- A non-developer completes the init interview and gets a working schema without editing config by hand.
- Drawer-scoped retrieval never returns content from another drawer (tested property).
- Hybrid search beats lexical-only and semantic-only search on the bundled evaluation sets.
- A non-developer uses tiroir daily across at least two machines without ever touching Git.
- Adding a second host adapter requires no change to the core.

## 13. Working process

1. ~~Read this brief, study the prior art in §3, and ask clarifying questions.~~
2. ~~Write the requirements with Delivery Kit~~ (`delivery/prd.md`, pending approval).
3. Record the architecture decisions and write the interface contracts (MCP tools, CLI, skills, adapter contract, schema format).
4. Decompose into milestones and tasks, then implement milestone by milestone. Start with the schema format, a synthetic dataset and the core read path, so a real store is usable as early as possible.

## 14. Decisions so far

- Concept names: the drawer metaphor is kept.
- Claude Desktop: memory on demand through MCP in v1 (no hooks there).
- Several drawers explicitly named in a prompt are all injected; an ambiguous name injects nothing.
- tiroir manages Git alone; it is the only writer to the shared history (option b). Server-side enforcement comes later (option c).
- Erasure (purge of a drawer, history included) is a v1 requirement.
- Session capture stays out of scope; it is left to other tools.
- Licence: Apache-2.0.
- Runtime: Python is preferred, to be confirmed by a decision record.
