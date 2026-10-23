---
name: careerfit-backend-maintainer
description: Maintain the CareerFit AI FastAPI backend in its established style. Use when implementing, refactoring, testing, or reviewing code under app/, especially API routes, SQLAlchemy models, Alembic migrations, configuration, authentication, document handling, and service boundaries.
---

# CareerFit Backend Maintainer

## Workflow

1. Read the affected route, schema, model, service, migration, and nearby tests
   before editing. Record pre-existing dirty paths.
2. Keep HTTP concerns in `app/api/`, reusable business work in `app/services/`,
   settings in `app/core/config.py`, and persistence definitions in `app/models.py`.
3. Match the existing synchronous SQLAlchemy pattern: inject `Session` with
   `get_db`, flush only when an ID is needed, and commit once the unit of work
   succeeds. Roll back or leave the transaction uncommitted on failure.
4. Guard every user-owned record by `user.id` and exclude soft-deleted rows.
   Treat company-scoped data as fixed reference data and guard reads by their
   company relationship; do not trust request IDs without lookup and scope
   checks.
5. Reuse `ok`, `dump`, and `not_found` from `app.api.common`; preserve the
   `{success, data, message}` response envelope and use meaningful 4xx errors.
6. Add or update focused pytest coverage for behavior changes. Run the narrowest
   relevant test first, then a broader backend check when practical.

## Persistence and migrations

- Prefer an Alembic revision for schema changes. Do not rely on
  `Base.metadata.create_all()` as a production migration strategy.
- Keep nullable columns, foreign keys, indexes, uniqueness, and soft-delete
  behavior aligned across SQLAlchemy models and Alembic.
- Never broaden a delete or update query beyond the validated owner/scope.
- Do not implement runtime create, update, delete, restore, upload, or reprocess
  operations for `COMPANY` data. This includes companies, departments,
  employees, job postings, performances, clients, and company documents.
- If the user explicitly requests a change to the fixed company corpus, apply
  it through version-controlled seed data or an Alembic migration, not CRUD.

## Route checklist

- Validate input with a Pydantic schema rather than ad-hoc dictionaries.
- Check authentication and record ownership before reading or mutating data.
- Do not expose direct company, company-resource, or company-document HTTP
  endpoints, including reads. Access fixed Samsung data only through internal
  mock-interview RAG retrieval.
- Preserve route prefixes and response compatibility unless an explicit API
  versioning decision accompanies the change.
- Do not expose secrets, session tokens, local paths, internal exception text,
  or another user's documents in a response.

## Handoff

Work only on paths named by the orchestrator. Return the requirement, production
paths changed, migration impact, diff summary, decisions, exact test
commands/results, and assumptions for the verifier. Do not self-approve or
request verification directly.

## Verifier feedback

Apply every finding from the orchestrator, regardless of severity. Make the
smallest safe fix, update focused tests, rerun relevant checks, and return a new
handoff. Do not dismiss or defer a finding without an explicit user decision.
