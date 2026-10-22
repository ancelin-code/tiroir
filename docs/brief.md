# tiroir — Product Brief

> **tiroir** (French for *drawer*): configurable, scoped memory for AI agents.
>
> This brief describes **what** we are building and **why**, the principles and the hard constraints. It deliberately leaves most **how** decisions open. The requirements live in [`delivery/prd.md`](../delivery/prd.md); every significant design decision is recorded as a decision record (context → options → decision → consequences).

## 1. Vision

Give any AI agent a memory organized the way its user actually works.

A developer thinks in repos and services. An accountant thinks in client files. A consultant thinks in engagements, a researcher in projects and papers. Existing agent memory tools hard-code one organization, usually "coding projects". tiroir makes **the organization of memory a configuration**: the user declares their *drawers* (scopes), and tiroir handles storage, indexing, retrieval, context injection and shared history.

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
4. **Usable by non-developers** from Claude Desktop, the web and mobile, with nothing to install, and not only by developers in a terminal.
5. **Team-ready**: one self-hosted server shares memory between members with per-store access, and keeps its history in Git, fully managed by tiroir.

## 4. Principles

1. **Plain files are the truth.** Memory is human-readable Markdown in a Git repository, readable without tiroir. Every index is derived and rebuildable.
2. **tiroir owns the history.** tiroir manages Git autonomously and transparently; users never touch Git. It is the only writer to a store's history; technical users may clone a store read-only.
3. **Self-hosted and private by default.** No telemetry. Memory stays on a server the user's organisation controls (a VPS or its own machine), and embeddings are computed there. An external embedding service is used only for a store whose administrator chose it.
4. **Isolation over recall.** When drawers are active, retrieval stays inside them. Searching across drawers is explicit.
5. **Abstain rather than mislead.** Injecting nothing is better than injecting a plausible but wrong memory.
6. **Humans own the synthesis.** Raw entries are append-only. Rewriting a summary requires user confirmation. The only deletion is an explicit, confirmed purge.
7. **Configuration over code**, with sensible defaults and presets so that the zero-config path still works.
8. **Harness-agnostic by design, Claude-first in delivery.** The core never depends on a specific agent host.

## 5. Core concepts

The metaphor is kept as the product vocabulary.

| Concept | Meaning |
|---|---|
| **Server** | One self-hosted installation of tiroir, serving one organization: its stores and members. |
| **Store** | A Git repository on the server holding one memory (an organization's, a team's, or one person's), with access granted per member. |
| **Drawer type** (scope type) | A user-declared kind of scope: `client`, `project`, `repo`, `engagement`… with its metadata schema, templates and detection rules. |
| **Drawer** (scope) | One instance: client C042, the repo `api-gateway`… |
| **Shared space** | Store-level knowledge that does not belong to one drawer: procedures, conventions, templates, preferences. |
| **Entry kinds** | A *summary* (curated, rewritable with confirmation) and a *log* (append-only, dated). Further kinds are deferred. |
| **Schema** | The configuration file declaring drawer types, layout, metadata, templates, detection, injection policy and language. |
| **Preset** | A ready-made schema for a common use case (developer, accounting firm, consulting…). |
| **Adapter** | The thin integration layer for one agent host (hooks, install, config wiring). |

## 6. Target users

- **Professional (non-developer)**: confidential, scope-per-client memory, from Claude Desktop, the web or mobile, possibly moving to Claude Code later. Installs nothing: a server is provided to them. The primary target.
- **Small team**: one server, several stores, members with access per store.
- **Administrator**: installs and runs the server on a VPS or their own machine; may be an IT provider.
- **Developer (solo)**: runs their own server, on their machine or a VPS; memory per repo or project, mostly in Claude Code.

## 7. Functional requirements

The detailed, checkable requirements are in [`delivery/prd.md`](../delivery/prd.md). In short:

**Must have (v1)**

- A declarative **schema** for drawer types, layout, metadata (with validation), templates, detection rules, injection policy and language.
- An **init skill**: an agent-guided interview that proposes a schema, generates config, templates and conventions, validates them, and can be safely re-run.
- **Schema migration**: evolve the schema (add a field, rename a type, change the layout) without losing data, with a dry run.
- **Presets**: at least `developer` and `accounting-firm`, with synthetic examples only.
- **Hybrid search**: lexical search (exact identifiers, numbers, proper nouns) and semantic search with embeddings computed **on the server** (the best multilingual model the evaluation finds), or by an external service the administrator selects per store, plus metadata filters. Drawer-scoped by default when drawers are active.
- **Context**: detect the drawers explicitly named in a prompt (within a strict latency budget; several named drawers are all injected, an ambiguous name injects nothing) and inject their summaries; abstain below a confidence threshold. Nothing is loaded at session start: a memory skill, whose description is generated from the schema, tells the agent when to use tiroir, and the store's conventions load on first use in a session. On hosts without hooks (Claude Desktop) the skill is the trigger and context comes on demand through MCP.
- **Write operations for agents**: append a log entry, propose a summary update (as a diff), apply it after confirmation, create a drawer from its template.
- **Erasure**: purge a drawer or an entry from the store, its whole Git history, the index and every mirror, so that no write can bring it back.
- **Shared history**: concurrent writes from several members never lose data, with no Git knowledge required from anyone; read-only clones and optional outgoing mirrors for those who want the files.
- **Memory language** as a setting: it drives templates, conventions, the language the agent writes in, and lexical-search behaviour (diacritics, stemming).
- A **self-hosted server** installed with Docker Compose, with sign-in, a minimal web administration page (members, stores, access, embeddings, mirrors), backup, restore and one-command upgrade.
- A **remote MCP server** usable from Claude Desktop, the web, mobile and Claude Code.
- A **Claude Code plugin** (prompt hook and one-command install).
- A **CLI** for technical members (search, read, log, doctor, migration, purge) and for the administrator (members, stores, access, index, backup, upgrade).
- An **evaluation harness** on synthetic datasets (recall@k, MRR, abstention false positives, comparing lexical, semantic and hybrid) shipped in the repo, so users can evaluate and calibrate their own configuration. Promoted from Should because the abstention threshold must be calibrated per embedding model.

**Should have**

- Clear onboarding and offboarding for team members.
- Refusing to write recognised credentials.
- Compatibility with the Agent Memory Repo format.

**Later**

- A **hosted offering**: tiroir run for several organizations, with sign-up and billing. v1's design must not preclude it.

**Out of scope for v1**

Automatic capture or compression of whole sessions, document ingestion (PDF, email, exports), a web UI for reading or editing memory, fine-grained per-drawer permissions (access is per store), writing through Git, offline use, single sign-on, adapters for hosts other than Claude, encryption at rest by tiroir (left to the server's disk encryption), and multi-organization hosting.

## 8. Non-functional requirements

- **Privacy**: the server sends nothing out beyond configured mirrors, a store's chosen external embedding service, the one-time model download, certificates and OAuth client metadata. No client content in logs, commit messages or error output.
- **Lightweight**: a small VPS (4 vCPU, 8 GB, no GPU) is enough; minimal, justified dependencies. Performance budgets are set in the PRD (prompt-hook latency, search latency, indexing time, memory).
- **Cross-platform**: the server runs on Linux, and on macOS or Windows through a container runtime; members use any platform their Claude host runs on.
- **Non-developer friendly**: members connect a host with the server's address and a sign-in, without installing anything or opening a terminal.
- **Documentation and examples** good enough to adopt tiroir without reading the code.
- **Open source** under Apache-2.0.

## 9. Architecture

**v1 is a self-hosted server**: a Docker Compose stack, on a VPS or the administrator's own machine, holding each store as a Git repository it alone writes, one index per store, the embedding model, and a remote MCP server with sign-in. Members reach it from Claude Desktop, the web, mobile and Claude Code; nothing is installed on their machines. A server on one's own machine covers local use, so there is no separate local mode. Remote MCP connectors in Claude are reached from Anthropic's infrastructure, so a server used from Claude Desktop, the web or mobile must be reachable from the internet over HTTPS.

**Git**: the source of truth, held by the server. Technical members may clone a store read-only; the administrator may mirror it to any Git remote over SSH or HTTPS.

The design must not preclude a **hosted offering** later (several organizations on one service).

The technical decisions are recorded in `delivery/decisions/`: runtime (Python in a container image), members and access, index, embeddings, retrieval, detection, process model, Git on the server, purge, proposals, adapters and skills, links, authentication and deployment.

## 10. Harness-agnostic roadmap

Layer the system so that only the outermost layer is host-specific:

1. **Core library and CLI**: no host dependency.
2. **Remote MCP server**: portable to any MCP-capable host.
3. **Skills**: init, migration, memory hygiene, using a portable skill format where possible.
4. **Adapters**: hooks and install per host. Only Claude Code ships in v1, but the adapter interface is designed now, and a second adapter should be cheap to add.

## 11. Design test: a small professional practice

A running design test for every decision, embodied by the `accounting-firm` preset:

- the owner works in Claude Desktop, the web or mobile, and may move to Claude Code; collaborators join later;
- one drawer per client, holding a structured summary (legal form, tax and VAT regime, fiscal year end, engagements, contacts, points of attention, deadlines) and a dated log;
- shared space for procedures, templates, a fiscal calendar and writing preferences;
- confidential data on a server the firm controls (a VPS, installed by its IT provider), embeddings computed on that server, a right to erasure;
- French as the memory language.

Real deployments keep their stores (data and configuration) on their own servers. The public tiroir repository only ships presets with synthetic data.

## 12. Success criteria

- An administrator goes from a fresh VPS to a member searching a store from Claude Desktop in under 30 minutes.
- A non-developer completes the init interview and gets a working schema without editing config by hand.
- Drawer-scoped retrieval never returns content from another drawer (tested property).
- Hybrid search beats lexical-only and semantic-only search on the bundled evaluation sets.
- A non-developer uses tiroir daily from their computer and their phone without installing anything or touching Git.
- Adding a second host adapter requires no change to the core.

## 13. Working process

1. ~~Read this brief, study the prior art in §3, and ask clarifying questions.~~
2. ~~Write the requirements with Delivery Kit~~ (`delivery/prd.md`, approved).
3. Record the architecture decisions and write the interface contracts (in review).
4. Decompose into milestones and tasks, then implement milestone by milestone. Start with a walking skeleton: one server, one store, append a note and find it from Claude Desktop, to prove the remote connector, sign-in and deployment first.

## 14. Decisions so far

- Concept names: the drawer metaphor is kept.
- Claude Desktop: memory on demand through MCP in v1 (no hooks there).
- Several drawers explicitly named in a prompt are all injected; an ambiguous name injects nothing.
- tiroir manages Git alone; it is the only writer to a store's history. On the server, this holds by construction: there is no working copy, and clones are read-only.
- Erasure (purge of a drawer, history included) is a v1 requirement.
- Session capture stays out of scope; it is left to other tools.
- Licence: Apache-2.0.
- v1 is a self-hosted server, not local-first (2026-10-22): non-developers
  cannot set up Git hosts and keys, and a server reaches every Claude host,
  phones included. A local-first Rust design was approved the day before and
  replaced.
- Runtime: Python in a container image, under lightness rules checked in CI
  (ADR-002); Rust kept for a measured hot path only.
- Embeddings: the default model is chosen by the evaluation, within the
  server budget; an external service is an option per store.
- Access control is per store, not per drawer: a member uses several stores
  (for example company-wide, leadership, personal), each with a `personal` or
  `team` audience. Every write to a team store is shown with its audience and
  confirmed; writes default to the personal store.
- A single log entry can be purged, not only a whole drawer.
- Nothing is loaded at session start; a memory skill generated from the schema
  tells the agent when to use tiroir.
