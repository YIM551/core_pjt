# CareerFit AI Frontend Agent Guide

## Skills

Repository-local skills are stored under `./skills`. Read the matching
`SKILL.md` before changing production code.

- `careerfit-frontend-orchestrator`: Coordinate a frontend feature through one
  implementer, an independent verifier, and a repair loop. Use as the default
  entry point for `src/` changes.
- `careerfit-frontend-maintainer`: Build and maintain Vue pages, components,
  Pinia state, routing, styling, responsive behavior, and tests.
- `careerfit-api-integration-maintainer`: Maintain Axios calls, cookie
  authentication, uploads, API envelopes, and error behavior.
- `careerfit-frontend-reviewer`: Read-only review for UX states, accessibility,
  API-contract alignment, and responsive regressions.

## Local guidance

- Work from `frontend/` and preserve Vue 3, Vite, JavaScript, Vue Router, Pinia,
  and Axios.
- Use the shared `api` client. Successful backend payloads are unwrapped from
  `{ success, data, message }`; errors come from `error.message`.
- Keep credentials enabled for the HttpOnly session cookie. Never store the
  session token in browser storage.
- Pages own data orchestration; reusable UI belongs in `components/`; global
  session state belongs in Pinia.
- Every async page needs loading, empty, success, and error-safe behavior.
- Preserve keyboard labels, focus visibility, touch targets, and mobile layout.

## Mandatory production-code workflow

For every change under `src/`, define owned paths and acceptance criteria,
delegate to one relevant maintainer, then use a fresh read-only
`careerfit-frontend-reviewer`. Repair every finding and repeat review until it
returns the exact phrase `0 findings`. Run `npm test` and `npm run build`.
