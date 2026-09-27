# Agent handoff protocol

Purpose: keep task state in the repository so Codex and Antigravity can alternate without relying on chat history.

This directory is subordinate to `AGENTS.md`. Nothing here overrides repository engineering rules, approved specifications, data contracts, or explicit user instructions.

## Required reading order for every agent

1. `AGENTS.md`
2. `agent_handoff/README.md`
3. `agent_handoff/CURRENT_STATE.md`
4. `agent_handoff/CURRENT_TASK.md`
5. `agent_handoff/DECISIONS.md`
6. `agent_handoff/BLOCKERS.md`
7. Relevant recent entries in `agent_handoff/TASK_LOG.md`
8. Task-specific repository specs/tests/code referenced by `CURRENT_TASK.md`

## Core operating rules

- The repository is the durable source of task state; chat memory is supplementary only.
- One task has one active implementation owner at a time.
- Codex and Antigravity must not concurrently edit the same task scope or the same files unless the user explicitly authorizes it.
- Either agent may implement or review. Prefer alternating roles: one implements, the other independently reviews.
- A reviewer must inspect the existing implementation first and report defects before rewriting anything.
- Never rewrite a working implementation from scratch merely because a different agent takes over.
- Preserve approved behavior and unrelated user changes.
- New dependencies, changed data semantics, destructive actions, or remote GitHub changes require the approvals defined in `AGENTS.md`.
- Secrets never belong in these handoff files, logs, commits, screenshots, or chat messages.
- `CURRENT_STATE.md` contains facts about the project now, not plans or speculation.
- `CURRENT_TASK.md` contains exactly one active task and its stop point.
- `DECISIONS.md` contains only explicit decisions already made for this project/task. Do not generalize them to unrelated tasks.
- `BLOCKERS.md` contains unresolved blockers only.
- `TASK_LOG.md` is append-only handoff history. Do not erase prior entries to make the current state look cleaner.

## Task lifecycle

Use one of these statuses:

`PLANNED -> IN_PROGRESS -> BLOCKED | IMPLEMENTED -> REVIEW_NEEDED -> REVIEWED -> APPROVED -> COMPLETED`

`IMPLEMENTED` means code/artifacts exist. It does not mean they passed independent review.

`COMPLETED` requires the applicable validation gates in `AGENTS.md` and the current task acceptance criteria to pass.

## Before editing

The active agent must state or record:

- task ID;
- intended files to create/change;
- implementation plan;
- dependencies needed;
- any ambiguity that would change business logic, data semantics, external dependencies, destructive behavior, or remote state.

If an ambiguity does not block safe independent work, mark only that component blocked and continue the rest.

## After work

Append a handoff entry to `TASK_LOG.md` containing:

- timestamp UTC;
- task ID;
- agent;
- role: implementation or review;
- status;
- files changed;
- tests/validation actually run and results;
- known issues or blockers;
- next safe action.

Update `CURRENT_STATE.md`, `CURRENT_TASK.md`, and `BLOCKERS.md` only when facts actually changed.

## Review protocol

When Agent B reviews Agent A:

1. Do not assume Agent A's success report is correct.
2. Inspect diff and relevant files.
3. Re-run applicable tests independently.
4. Verify source provenance, time-series integrity, causal boundaries, missing-value semantics, resume/idempotency, and secret handling where relevant.
5. Report defects first.
6. Do not modify defects until the user/task scope authorizes fixes.

## Parallel work

Parallel work is allowed only on disjoint task/file scopes. Record ownership in `CURRENT_TASK.md` or `TASK_LOG.md` before starting.

## Completed tasks

When a task is truly complete, copy its final task summary to `agent_handoff/completed/<TASK-ID>.md`, then replace `CURRENT_TASK.md` with the next active task. Do not delete historical log entries.
