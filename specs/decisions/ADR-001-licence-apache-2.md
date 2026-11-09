# ADR-001: License tiroir under Apache-2.0

**Status:** accepted
**Date:** 2026-10-21

## Context

The requirements (D3) make tiroir open source under a licence recorded here.
The licence decides who can adopt, embed and redistribute it, and whether
contributors' patents are covered.

## Decision

tiroir is licensed under the Apache License 2.0. The repository carries the
full text in `LICENSE`. Every source file may carry an SPDX header
(`SPDX-License-Identifier: Apache-2.0`); a `NOTICE` file is added when the
first third-party notice requires one.

## Alternatives considered

- **MIT** - equally permissive and shorter, but has no explicit patent grant
  or patent retaliation clause, which companies adopting a tool that handles
  their data look for.
- **AGPL-3.0** (Basic Memory's choice) - prevents closed SaaS reuse, but tiroir
  has no SaaS to protect and the AGPL deters the firms and teams it targets
  from adopting or extending it.

## Consequences

Anyone may reuse tiroir, including in a closed hosted service; that is
accepted. Contributors grant a patent licence on their contributions. Modified
files must say they were modified, and the name "tiroir" is not licensed for
forks. Dependencies must have licences compatible with Apache-2.0 (MIT, BSD,
Apache-2.0); a GPL dependency is excluded.
