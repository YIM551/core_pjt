---
name: careerfit-frontend-orchestrator
description: Coordinate CareerFit Vue production changes through one scoped implementer, a fresh independent reviewer, and a repair loop.
---

# CareerFit Frontend Orchestrator

1. Record dirty paths and define requirement, owned paths, API contracts,
   acceptance criteria, and checks.
2. Delegate to exactly one implementer. Use
   `careerfit-api-integration-maintainer` when transport or payload behavior is
   central; otherwise use `careerfit-frontend-maintainer`.
3. Require a handoff with owned paths, behavior/design decisions, API
   assumptions, accessibility/responsive impact, and exact checks.
4. Start a fresh read-only `careerfit-frontend-reviewer`.
5. Forward every finding to the same implementer for repair and retest, then
   repeat with a new reviewer.
6. Finish only after `0 findings`, `npm test`, and `npm run build`.
