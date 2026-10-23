---
name: careerfit-api-contract-reviewer
description: Independently review CareerFit AI FastAPI production-code diffs for API contract, immutable company-data policy, ownership, soft-delete, transaction, migration, upload, and RAG data-scope defects. Use after changes under app/ and before declaring backend work complete. This skill is read-only.
---

# CareerFit API Contract Reviewer

Do not edit files, run formatters, generate migrations, or run tests. Review
only production paths named in the developer handoff and the supplied diff;
ignore pre-existing dirty paths outside that ownership list.

## Review procedure

1. Read the diff, affected route/schema/model/service, and relevant tests.
2. Report every finding with severity, path, line, consequence, and a minimal
   fix. Do not decide whether the developer may defer a finding.
3. State each checklist item as pass, finding, or not applicable. Finish with a
   clear total-findings count. Return the exact phrase `0 findings` when there
   are none; otherwise return the findings to the orchestrator.

## Checklist

- **Contract:** routes retain `/api/v1` placement, use compatible request
  validation/status codes, and return the `ok()` envelope on success.
- **Fixed company data:** `COMPANY` resources have no direct HTTP APIs,
  including reads. Report any company, company-resource, or company-document
  route as a blocking finding; fixed Samsung data is internal RAG context only.
- **Authorization:** every user-owned lookup includes `user.id`; company and
  document scope are verified before access.
- **Soft delete:** normal reads exclude `deleted_at` records; mutations do not
  revive or overwrite deleted data accidentally.
- **Persistence:** writes have a coherent transaction, schema changes include a
  migration, foreign keys/indexes match usage, and queries are appropriately
  scoped.
- **Files and AI:** uploads are size/type constrained, local file paths are not
  exposed, and retrieved context cannot cross PERSONAL/COMPANY boundaries.
- **Failure paths:** malformed LLM output, extraction failure, missing records,
  and database errors produce safe behavior without leaking internals.
