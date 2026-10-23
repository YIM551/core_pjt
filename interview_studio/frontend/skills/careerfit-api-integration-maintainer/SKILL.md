---
name: careerfit-api-integration-maintainer
description: Maintain CareerFit frontend integration with FastAPI authentication, response envelopes, CRUD, multipart uploads, RAG chat, analysis, and interviews.
---

# CareerFit API Integration Maintainer

- Use the shared Axios instance with `/api/v1`, `withCredentials: true`, and the
  existing error interceptor.
- Treat `{ success, data, message }` as the only success envelope. Read failure
  text from `{ success: false, error: { code, message, details } }`.
- Never read, write, or expose the HttpOnly session cookie. On an unauthenticated
  initial `/auth/me`, route to login without retry loops.
- Send JSON for CRUD, analysis, chat, and interview calls. Use `FormData` with
  `file`, `title`, and `document_type` for uploads.
- Company and combined chat require `company_id`. A selected job posting must
  belong to the selected company. Do not infer IDs across scopes.
- Never cache sensitive document text or model answers in local storage.
- Compare every changed call to the matching FastAPI route and schema.

Test envelope unwrapping, readable errors, payload shape, disabled in-flight
actions, and at least one missing or empty response state.
