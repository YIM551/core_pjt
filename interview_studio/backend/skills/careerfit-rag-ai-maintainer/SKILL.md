---
name: careerfit-rag-ai-maintainer
description: Safely maintain CareerFit AI document ingestion, embeddings, vector retrieval, LLM chat, compatibility analysis, and mock-interview evaluation flows. Use when changing app/services/ai.py, app/services/documents.py, AI endpoints, prompts, retrieval scope, or structured LLM output.
---

# CareerFit RAG and AI Maintainer

## Retrieval and document rules

- Keep document and chunk scope consistent: `PERSONAL` data is constrained by
  the authenticated `user_id`; `COMPANY` data is constrained by validated
  `company_id`. A combined query applies both constraints independently.
- Treat the company corpus as fixed and read-only. Do not add company document
  upload, deletion, restoration, reprocessing, or embedding-regeneration APIs.
  Update company content only through an explicitly requested version-controlled
  seed or migration.
- Do not expose company corpus reads through HTTP. Retrieve the fixed Samsung
  corpus only inside mock-interview flows.
- Filter soft-deleted documents and chunks before vector ordering. Return source
  metadata only for chunks actually supplied to the model.
- Preserve the configured 768-dimension vector contract unless model, database
  column, backfill, and retrieval queries change together.
- For PERSONAL uploads, validate suffix, content size, extraction result, and
  processing state. Store generated filenames safely and never return
  filesystem paths.

## LLM rules

- Keep model URLs, keys, model names, and limits in `Settings`; never hard-code
  secrets or log prompts that include sensitive user documents.
- State prompt constraints explicitly: use supplied context, distinguish missing
  evidence, and return the requested language/structure.
- Parse structured responses through Pydantic. On network failure, timeout, or
  invalid model output, use a deterministic safe fallback and preserve a usable
  API response.
- Treat retrieved text and model output as untrusted; do not let either alter
  authorization, SQL, filesystem paths, or service configuration.

## Interview and analysis rules

- Derive interview sequence and completion state from persisted messages, not
  client-provided counters. Keep candidate answers, evaluations, and follow-up
  questions in one coherent transaction.
- Validate that the job posting belongs to the selected company before using its
  requirements. Explain score inputs enough for users to understand a result;
  do not present heuristic scores as objective facts.

## Validation

Add focused tests with deterministic embeddings/model stubs. Exercise at least
one scope-isolation case and one malformed-or-unavailable-model fallback case
for behavior changes.

## Handoff and verifier feedback

Work only on paths named by the orchestrator. Return changed production paths,
migration impact, retrieval/LLM decisions, and exact checks/results for the
verifier. Do not self-approve completion. Apply every verifier finding with the
smallest safe change, rerun relevant checks, and return a new handoff.
