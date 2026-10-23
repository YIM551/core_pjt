---
name: git-commit-korean
description: Inspect repository state, recent history, staged and unstaged diffs, then draft or create very small Korean gitmoji commits that match local conventions. Use when asked to write a commit message, create a commit, split mixed changes, or redo a mistaken commit.
---

# Git Commit Korean

## Prepare context

Read the repository root `AGENTS.md` when present. Read
`references/commit-style.md` before choosing messages and
`references/gitmoji-cheatsheet.md` when the change is outside the core patterns.

Before deciding boundaries, run:

```text
git status --short
git diff --staged
git diff
git log --oneline -n 10
```

For a redo or split of the latest commit, also run `git show --stat --summary
HEAD`. Treat the staged diff as state to inspect, not as an approved grouping.

## Split before staging

Plan the smallest coherent commit boundaries before staging. Split build and
environment setup, database migrations, shared infrastructure, API/domain
behavior, tests, documentation, and cleanup whenever independently reviewable.

- Split when a subject naturally needs `and`, `및`, or `그리고`.
- Prefer infrastructure before the code that consumes it.
- Use partial staging when a file contains separate concerns.
- Keep unrelated pre-existing user changes out of commits.
- When uncertain, split; a single meaningful configuration or migration change
  may be its own commit.

## Commit style

Write a one-line Korean subject in this form:

```text
<optional gitmoji> <type>: <구체적인 한국어 요약>
```

Prefer local history, then use the reference mapping. Keep the message focused
on the reviewable behavior rather than the editing process. Avoid vague subjects
such as `수정` or `변경`.

## Execute safely

When asked only for messages, provide one to three candidates per logical
commit and recommend one. When asked to commit:

1. Inspect the complete repository state.
2. Build and stage only the first logical unit; rebuild a mixed staging set.
3. Create its Korean commit, then run `git status --short` and
   `git diff --staged`.
4. Repeat for remaining intended changes and report each hash, subject, and
   scope.

Do not amend, rebase, squash, reset, or rewrite history unless explicitly
requested. Do not create a catch-all commit merely to clean the worktree.
