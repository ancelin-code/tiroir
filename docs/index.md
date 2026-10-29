# tiroir

**Configurable, scoped memory for AI agents.** *Tiroir* is French for *drawer*.

tiroir gives AI agents a memory organised the way their users actually work. A
developer thinks in repositories, an accountant in client files, a consultant
in engagements. With tiroir, that organisation is configuration: a store holds
drawers, and tiroir handles storage, indexing and retrieval. Memory is plain
Markdown in a Git repository on your own server; nothing leaves it.

## Who it is for

- **Administrators** who run one tiroir server for themselves or their team, on
  a VPS with Docker Compose.
- **Members** of that team who connect Claude Desktop to the server, then ask
  Claude to search their memory and to log what happened.

## What version 0.1.0 does

- One server, started with Docker Compose behind Caddy, which obtains the HTTPS
  certificate by itself. The image is published for `amd64` and `arm64`.
- Members, personal and team stores, and read or write access, managed with
  the [administration CLI](reference/cli.md) inside the container.
- A store starts from a preset. The one bundled preset, `accounting-firm`,
  comes with invented client drawers to try the server on.
- Claude Desktop connects as a custom connector, signs in with OAuth, and gets
  four tools: search, read, log, and the list of the stores the member can
  reach.

## Where to start

1. [Install tiroir on a VPS](install/vps.md): the stack, the first
   administrator, a member and a store.
2. [Connect Claude Desktop](connect/claude-desktop.md): add the server as a
   custom connector and sign in.
3. [CLI reference](reference/cli.md): every administration command, with its
   arguments and an example.

tiroir is open source under the Apache-2.0 licence; its code is on
[GitHub](https://github.com/ancelin-code/tiroir).
