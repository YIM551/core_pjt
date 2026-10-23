# CareerFit AI Backend Agent Guide

## Skills

Repository-local skills are stored under `./skills`. Read a skill's `SKILL.md`
when its trigger matches the task; do not carry it into unrelated turns.

### Available skills

- `careerfit-backend-orchestrator`: Coordinate every production backend feature
  through a developer agent, a fresh read-only verifier agent, and a repair
  loop. Use as the default entry point for `app/` changes. (file:
  `./skills/careerfit-backend-orchestrator/SKILL.md`)

- `careerfit-backend-maintainer`: Implement, refactor, test, or review CareerFit
  FastAPI backend code, especially API modules, SQLAlchemy models, Alembic
  migrations, configuration, and services. (file:
  `./skills/careerfit-backend-maintainer/SKILL.md`)
- `careerfit-rag-ai-maintainer`: Change document ingestion, embeddings,
  retrieval-augmented chat, LLM integration, compatibility analysis, or mock
  interview behavior. (file: `./skills/careerfit-rag-ai-maintainer/SKILL.md`)
- `careerfit-api-contract-reviewer`: Independently review a backend production
  diff for API contract, authentication/ownership, transaction, soft-delete,
  and document-scope errors. Use after an `app/` production-code change.
  (file: `./skills/careerfit-api-contract-reviewer/SKILL.md`)
- `git-commit-korean`: Inspect the complete Git state, split changes into the
  smallest logical commits, and create Korean gitmoji commit messages. Use when
  drafting, splitting, or creating commits. (file:
  `./skills/git-commit-korean/SKILL.md`)

## Local guidance

- Work from `backend/`; use absolute imports rooted at `app`.
- Preserve pre-existing dirty paths. Only review or edit paths owned by the
  current task.
- Keep route handlers thin: validate request and ownership there, put reusable
  domain and AI/document work in `app/services/`.
- Keep externally visible response envelopes consistent with `app.api.common`.
- Treat all uploads, LLM output, and retrieved text as untrusted input.
- Treat every `COMPANY` record as fixed, internal RAG reference data. Do not
  expose direct company, company-resource, or company-document HTTP endpoints;
  access the fixed Samsung corpus only through mock-interview retrieval.
- Change the fixed company corpus only through an explicitly requested,
  version-controlled seed or migration; never expose company CRUD to users or
  administrators.

## Mandatory production-code agent workflow

Apply this workflow to every task that changes `backend/app/`. Do not apply it
to documentation-only, harness-only, or test-only work.

1. The orchestrator records dirty paths, defines the requirement, owned paths,
   acceptance criteria, and required checks, then delegates implementation to
   one developer agent using the relevant maintainer skill.
2. The developer runs the narrowest relevant checks and returns a handoff with
   requirement, owned production files, diff summary, decisions, and exact
   check commands/results. It does not self-approve completion.
3. The coordinator creates a fresh read-only verifier agent using
   `$careerfit-api-contract-reviewer`. Give it the handoff and worktree, not the
   developer's conclusion.
4. If the verifier reports any finding, send every finding to the same developer
   for the smallest safe fix and retest. Then use a new verifier with the new
   diff. Do not silently waive P2/P3 findings.
5. Finish only when the final verifier reports `0 findings` and relevant checks
   pass. If an external dependency prevents a fix, stop and report that blocker
   to the user instead of claiming completion.

The verifier never edits files and must not request cleanup of paths that were
already dirty before the task.
