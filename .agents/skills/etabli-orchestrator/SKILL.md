---
name: etabli-orchestrator
author: Ancelin Serre
description: >-
  The project's delivery assistant and the entry point of Établi. Answers where
  the project stands, what to do next, and who is working on what, from specs/ and git;
  and routes any request to build or change the project through requirements, design,
  decomposition, benches and review, holding the approval gates and the bench policy. Use for
  "what's next", "what's the status", progress, blockers, or any new work on a project
  that has a specs/ directory or asks to start one. Delegates the work itself to the
  other Établi skills; it does not write requirements, code, or pull requests.
license: Apache-2.0
repository: https://github.com/ancelin-code/etabli.git
product-version: etabli@v0
version: "0.2.0"
keywords:
  - etabli-workflow
  - orchestrator
  - parallel-benches
  - decomposition
  - approval-gates
spec-version: "1.0"
compatibility:
  - git@>=2.30
  - gh@>=2.0
metadata:
  category: development
  owner: ancelin-code
---

# Établi Orchestrator

The entry point to Établi: it routes a project from intent to merged
work, deciding **what happens next** and **where a human must approve**. It does
not do the work itself.

Établi is the family of skills named `etabli-orchestrator` and `etabli-*`. They are one workflow, not a menu:
each phase consumes the file the previous one wrote, so a phase cannot start
before the phase ahead of it has written its artifact. Reach the other skills
through this one.

## Where the project stands

For "what's next", "what's the status", "who is on what", and before starting
any phase, run this from the repository root and answer from its output:

```sh
sh <skill-root>/scripts/where.sh
```

It prints each phase's artifact and whether it is approved, the task rows and
their derived state, and one or more `NEXT` lines stating what to do now. Do not
re-derive any of it by reading files or git: the script applies the rules below.
Exit 1 means state could not be read, usually `gh`; report the error, do not
guess.

For every task in review it also prints `REVIEW` rows, one per lens: the task,
its pull request, the lens, the review skill mapped to it, and why the lens
applies (`default`, `task`, `label`, or `path:<file>`). List each task in review
with its pull request and the skills to run on it. A skill of `-` means no skill
is mapped: suggest the harness's own review through that lens, and mention that
a skill can be mapped in `specs/review-lenses.conf`. When a named skill is not
installed, say so by name rather than substituting another. The file's format
is in the [review lenses](references/conventions.md#review-lenses) convention.

A `NEXT repair-install` line means Établi's skills are not all installed side
by side, so a phase would run without one of its siblings. Stop, and show the
user that line: repairing the install is theirs to do.

A `NEXT install-routing` line means this project's `AGENTS.md` does not yet send
requests here. Run the command it names once, and mention it in the answer.

## Conventions

Read [Établi conventions](references/conventions.md) once per run. It defines
what a project, an epic and a task each are, plus the task schema, branch
names, claims, tiers and pull request rules, and the other skills rely on
it rather than repeating those rules. It also fixes where every artifact below
lives: all paths here are relative to the repository root, under `specs/`.

## The workflow

Each phase ends by writing a file. The next phase starts from that file in a
fresh context, so a long session never has to stay alive to carry state.

| Phase | Produces | Delegate to | Gate |
|---|---|---|---|
| Requirements | `specs/prd.md` | `etabli-spec` (stage A) | **Human approves** |
| Design spine | decision records in `docs/adr/`, `docs/decisions/` or `specs/decisions/`, and `specs/contracts/<interface>.md` | `etabli-spec` (stage B) | **Human approves** |
| Decomposition | `specs/decomposition.md`, plus `specs/tasks/<id>.md` per task | `etabli-decompose` | **Human approves** |
| Benches | a draft pull request per task | `etabli-status`, then `etabli-implement`, then `etabli-refine` | none, runs unattended |
| Review | findings on the pull request | the review skill each `REVIEW` row names, else the harness review | **Human approves the merge** |
| Milestone review, when the plan has milestones | `specs/milestones/<slug>.md` | `etabli-decompose` | **Human approves** |

Approval gates sit on **artifacts**, not on steps. Once decomposition is
approved, benches run unattended up to a draft pull request. Pull request review is
the final gate.

A full workflow is cut in milestones unless the user decided against them, and
goes round the last three phases once per milestone, as the
[Établi conventions](references/conventions.md#milestones) define.
`where.sh` prints a `MILESTONE` row for each, and `NEXT review-milestone`,
`approve-milestone-review` or `decompose-milestone` at the boundary. Never cut
or start the next milestone before its predecessor's review note is approved:
that stop is the point of having milestones. When the review decides to
revise, route the revision to `etabli-spec`; the gates it reopens hold the
next cut back by themselves.

## Choosing the ceremony

Investigate before choosing depth. Read the request and the code, then pick:

- **Direct implement** for a single well-understood change with obvious
  acceptance criteria, belonging to no epic.
- **Full workflow** when the work spans several tasks, needs contracts so that
  parallel work stays consistent, or touches a decision worth recording.

Choosing the full workflow for a one-task change wastes a day of ceremony.
Choosing direct implement for genuinely parallel work produces conflicting code.

Whether a full-workflow set runs in parallel is decomposition's finding, not a
choice made here: tasks marked `parallel: false` run alone, and a set that
serializes marks them all. The phases and gates are the same either way. When
one person holds a serial set, skip the launcher and invoke `etabli-implement`
then, in a separate session, `etabli-refine` per task in dependency order; the claim only earns its keep when several people
pick from the same tasks.

### Direct implement

Write one task file, `specs/tasks/<id>.md`, from
`<etabli-decompose>/assets/task.template.md`, then invoke `etabli-implement`
on it in the ordinary checkout. Then run `etabli-refine` on the same task file
in a separate session, on a stronger model when the harness lets you choose one.
Never in the session that implemented: a reviewer that wrote the change defends
it. Do not ask whether to review; end by giving the exact command that starts
the second session. Nothing else in this skill applies.

Skip the claim, the worktree, the launcher, `etabli-status` and all three
approval gates. Those coordinate concurrent benches and guard artifacts this path
does not produce. Do not create an epic, and do not run
`<etabli-decompose>/scripts/validate-tasks.sh`: it enforces the full schema
and will reject a task trimmed for this path.

Keep the task file. `etabli-implement` halts without explicit acceptance
criteria, and the file is what the diff is checked back against and what the
pull request points at. Only `id` and `title` carry meaning here: the dependency
and conflict fields order benches, and `tier` routes a launcher that never runs.

Commit and open the pull request as usual afterwards. Review is unchanged.

## Starting a phase

1. Check that the delegate skill is installed. If it is not, stop and name the
   skill the user needs to install. Do not improvise its job.
2. Confirm from `where.sh` that the previous phase's artifact exists and was
   approved. An unapproved artifact is the signal to stop and ask, not to
   proceed.
3. Load only that phase's inputs. Phases communicate through files.

## Bench policy

- one task, one branch, one worktree, one pull request
- claim before starting, by invoking the `etabli-status` skill. A task reported
  as held is taken: choose another rather than retrying
- at most three benches at once, regardless of how many tasks are ready
- never start two tasks that list each other in `conflicts_with`, even when both
  are ready
- a task marked `parallel: false` runs alone: nothing else of the set in flight
  while it does
- a bench that reveals its task is wrong **stops**. Save the attempt, revert, and
  raise it. Do not widen scope to make a bad task work

Start benches with the launcher, which claims, creates the worktree, starts the
session and publishes its result as a draft pull request, and refuses a task
whose claim it loses:

```sh
sh <skill-root>/scripts/launch-benches.sh --dry-run <task-id>...
```

Once the first benches are launched, keep the set moving with the follow loop
instead of polling `where.sh`:

```sh
sh <skill-root>/scripts/follow.sh -- <the launcher options you used>
```

It launches each task as the merges it depends on land, within the same limits,
and prints one line per event: `PUBLISHED`, `MERGED`, `LAUNCHED`, `BENCH-FAILED`,
and `COMPLETE`, `MILESTONE` or `STUCK` when it exits. `MILESTONE` means the
current milestone needs a person: tell the user, and take up its review. Run it in the background where the
harness reports a background command's output as it arrives, and tell the user
about the lines that need them: a pull request to review, a failed bench, a stuck
set. Where it does not, add `--exit-on-human`: the command ends (exit 4) when a
bench publishes or fails, as it already does for `MILESTONE`, `STUCK` and
`COMPLETE`, so its end is the notification. Tell the user, then run it again. Merging stays with the user; the loop never merges.

The full lifecycle, the limits and what to do when a bench does not finish are in
[benches](references/benches.md). The review budget and the two lenses worth running
are in [review](references/review.md).

## Stopping rules

Stop and hand back to a human when any of these holds:

- an artifact needed by the next phase is missing or unapproved
- a required delegate skill is not installed
- two repair attempts on the same failure have not fixed it
- implementation shows the requirements are wrong

Re-review only when review found a high-severity issue, or three medium findings
plus at least two low ones. Otherwise one review pass is the budget.

## Boundaries

The harness owns permission modes, plan mode, worktree isolation and model
selection. This skill does not re-implement them, and does not wrap git or pull
request commands the harness already performs well.

## Supporting Files

- [Position](scripts/where.sh) - phase states, task states and the next action,
  in one call
- [Routing installer](scripts/install-routing.sh) - adds
  [the routing block](assets/agents-routing.md) to the project's `AGENTS.md`
  a [starter review lenses file](assets/review-lenses.conf), idempotently
- [Bench launcher](scripts/launch-benches.sh) - claims a task, creates its worktree,
  and starts an unattended session, capped and conflict-aware
- [Bench publisher](scripts/publish-bench.sh) - commits a finished bench, pushes it,
  and opens its draft pull request; the launcher runs it
- [Follow loop](scripts/follow.sh) - launches tasks as their dependencies
  merge and reports each bench's outcome, until the set is merged or stuck
- [Bench release](scripts/release-bench.sh) - gives the task back when a bench's
  session failed without doing anything; the launcher runs it

## Acceptance Criteria

- every phase transition happened through a file, not a live session
- each artifact gate, including a milestone's review note, was approved by a human before the next phase
- no bench ran on a task claimed by somebody else, and no two conflicting tasks ran together
- a missing delegate skill was reported by name instead of being improvised
