# ADR-004: Keep stores self-describing and list them in a per-machine configuration

**Status:** proposed
**Date:** 2026-10-21

## Context

A machine uses several stores (M1), each with an audience (M2), and writes
whose target is not implied go to the user's personal store (M4). Every
component needs to know which stores are in use, where they are, who the user
is (Y4f) and which store is the default, and none of this may leak into a
store shared with others.

## Decision

- **What belongs to the store**, shared by everyone who clones it, lives in its
  `tiroir.yaml`: a store id (UUID generated at creation), a name, the audience
  (`personal` or `team`) and the memory language.
- **What belongs to the machine** lives in one configuration file in the
  user's configuration directory (the platform's standard location, through
  the `directories` crate), file `config.yaml`:
  - the user's identity: a handle (slug used in log file names and commits)
    and a display name;
  - the stores in use: their local path and remote URL, keyed by store id;
  - the default store for writes whose target is not implied; it must be a
    `personal` store when one exists.
- **What tiroir derives per machine** (indexes, keys, pending proposals,
  session markers, locks) lives in the user's data directory
  (the platform's standard data location), in one subfolder per store id.
- Store working copies default to a visible `Tiroir/<store name>` folder in
  the user's home directory, so a non-developer can find and read them.

## Alternatives considered

- **Audience in the machine configuration** - lets each user label a store
  differently, so the same team store could be "personal" on one machine and
  silently skip write confirmation (W5).
- **One store per machine, with sub-stores as folders** - cannot give
  different people different access, which is the reason stores exist (M1).
- **Store list inside a "home" store** - one more repository to sync before
  anything works, and it would publish machine paths to a remote.

## Consequences

Adding a store on a new machine means cloning it and adding one entry to the
local configuration, which `tiroir store connect` (or the equivalent MCP
action) does. Removing a person from a team store is done on the Git host;
their existing clone keeps what it already had (documented, H1). Because the
store id keys everything machine-side, renaming a store or moving its folder
does not orphan its index or keys.
