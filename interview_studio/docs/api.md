# CareerFit API v2

Base URL: `http://localhost:8000/api/v2`. All successful non-SSE responses are raw JSON resources or arrays. Authentication uses the `careerfit_session` HttpOnly cookie created by `POST /auth/session`.

## Session

| Method | Path | Success |
| --- | --- | --- |
| POST | `/auth/session` | `201` user JSON and session cookie |
| GET | `/auth/session` | `200` current user JSON |
| DELETE | `/auth/session` | `204` |

## Candidate and documents

| Method | Path | Success |
| --- | --- | --- |
| GET, POST | `/candidate/documents` | document array / `201` document JSON |
| POST | `/candidate/documents/{documentId}/reprocess` | document JSON |
| DELETE | `/candidate/documents/{documentId}` | `204` |
| POST | `/candidate/chat` | `{ "answer": string, "sources": [{ "category": string, "title": string }] }` |

Uploads are multipart form data (`file`, optional `title`, optional `document_type`) and are limited to the configured file policy. File paths, extracted text, chunks, embeddings, tool payloads and corpus URLs are never returned.

## Interviews

| Method | Path | Success |
| --- | --- | --- |
| POST, GET | `/interviews` | `201` session detail / session array |
| GET | `/interviews/{sessionId}` | session and messages |
| POST | `/interviews/{sessionId}/messages` | saved candidate/interviewer messages and sanitized sources |
| POST | `/interviews/{sessionId}/messages/stream` | SSE (`status`, `token`, `complete`, `error`) |
| POST | `/interviews/{sessionId}/finish` | completed session |
| GET | `/interviews/{sessionId}/report` | report JSON after completion |

The interview and personal chat use native Qwen tool calls. When the model fails the required tool protocol three times, the API responds with `503 LLM_TOOL_CALLING_UNAVAILABLE` and does not save the candidate turn.

## Errors

Errors use `application/problem+json` (RFC 9457):

```json
{
  "type": "urn:careerfit:problem:validation_error",
  "title": "Validation Error",
  "status": 422,
  "detail": "요청 값이 올바르지 않습니다.",
  "code": "VALIDATION_ERROR",
  "errors": []
}
```

Common codes are `AUTHENTICATION_REQUIRED`, `RESOURCE_NOT_FOUND`, `RESOURCE_CONFLICT`, `VALIDATION_ERROR`, `EMBEDDING_SERVICE_UNAVAILABLE`, `LLM_TOOL_CALLING_UNAVAILABLE`, and `INTERNAL_ERROR`.
