---
id: skill-002
title: Serve the member's account page with the memory skill download
type: feat
epic: skill
depends_on: [skill-001]
parallel: true
conflicts_with: [semantic-003, semantic-004, context-004, presets-001, eval-001, eval-003, guides-001]
tier: build
review: [security]
---

## Context

The member downloads their memory skill from their account page, which says
when the downloaded copy is out of date (ADR-013). The
[HTTP routes contract](../contracts/http-routes.md) fixes `/account` and
`/account/skill.zip`, both behind the web session of the sign-in pages built
by `server-002`. Only the parts this milestone needs are built: the stores
and access, the skill, and the existing password change. Personal access
tokens come with the operations milestone.

## Covers

- C5c
- C7 (part): the memory skill page with its upload steps and the
  project-instructions snippet that reinforces it; the scripted acceptance
  run is `guides-002`'s

## Scope

Files this task is expected to touch:

- `src/tiroir/server/auth/pages.py`: `GET /account` (the member's stores with
  audience and access, the skill's freshness and a download button, a link to
  change the password), `GET /account/skill.zip` (`MemberContext.memory_skill`,
  `Content-Disposition: attachment`); `303` to `/signin?next=…` without a
  session
- `src/tiroir/server/templates/account.html`: the page, in English, same
  style, CSP and no third-party resource as the sign-in pages; no memory
  content
- `src/tiroir/server/app.py`: only if the routes need registering there
- `tests/integration/test_account.py`
- `docs/connect/memory-skill.md` (new, added to the `nav` of
  `zensical.toml`): what the memory skill is, downloading it from the account
  page, when it goes out of date and how to update it, uploading it in Claude
  Desktop and on the web, and a project-instructions snippet in French and in
  English (C7)

Out of scope:

- personal access tokens on the account page (operations milestone)
- the administration page (team milestone)
- the Claude Desktop connector guide and the per-host table (`guides-001`)

## Acceptance criteria

- A signed-in member opening `/account` sees their stores with audience and
  access and "Your memory skill is up to date" or "out of date", and no
  store they are not granted.
- `/account/skill.zip` downloads the archive of `skill-001`; afterwards the
  page says the skill is up to date; after an administrator grants a new
  store, it says it is out of date.
- Without a session, both paths answer `303` to `/signin?next=…`.
- The page sets the same Content-Security-Policy as the sign-in pages, loads
  no third-party resource, and the request log holds no query string.
- The snippet is under 80 words in each language and names the memory skill
  and tiroir's tools by their names.
- `mise run docs:build` passes with the new page in the nav; `mise run check`
  passes.

## Validation

`mise run test -- tests/integration/test_account.py`, `mise run docs:build`,
then `mise run check`.
