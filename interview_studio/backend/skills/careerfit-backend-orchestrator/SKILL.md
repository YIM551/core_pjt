---
name: careerfit-backend-orchestrator
description: Coordinate every CareerFit AI FastAPI production-code change through a scoped developer agent, an independent read-only API-contract verifier, and a repair loop. Use when a task changes backend/app, including API, model, migration, document, RAG, analysis, or interview behavior.
---

# CareerFit Backend Orchestrator

## Workflow

1. Inspect the request and worktree. Record pre-existing dirty paths. Define
   the requirement, owned production paths, acceptance criteria, migration
   impact, and required checks before delegation.
2. Delegate implementation to exactly one developer agent:
   - Use `$careerfit-rag-ai-maintainer` for document ingestion, embeddings,
     retrieval, LLM, compatibility analysis, or interview behavior.
   - Use `$careerfit-backend-maintainer` for every other `app/` change.
3. Require a developer handoff containing the requirement, owned paths, diff
   summary, decisions, migration impact, and exact test commands/results.
4. Start a fresh `$careerfit-api-contract-reviewer` agent after implementation.
   Give it the developer handoff, owned paths, and current diff. Keep it
   read-only; it must not edit files or run mutating commands.
5. If the verifier reports any finding, forward all findings unchanged to the
   same developer agent. Require the smallest safe fixes and retesting. Start a
   new verifier with the updated diff.
6. Report completion to the user only after the verifier explicitly returns
   `0 findings` and required checks pass. If an external dependency prevents a
   fix, report the blocker instead of completing the task.

## Boundaries

- Do not delegate documentation-only, harness-only, or test-only tasks through
  this workflow unless the user requests independent review.
- Never let the verifier review or clean paths that were dirty before the task.
- Keep implementation and verification sequential. The verifier reviews a
  completed developer handoff, not work in progress.
