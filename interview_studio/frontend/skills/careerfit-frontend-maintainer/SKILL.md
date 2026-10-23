---
name: careerfit-frontend-maintainer
description: Maintain CareerFit AI Vue pages, components, routing, Pinia state, styles, responsive behavior, accessibility, and frontend tests.
---

# CareerFit Frontend Maintainer

1. Read the affected page, shared layout, router, store, API client, and nearby
   tests. Record pre-existing dirty paths and edit only owned paths.
2. Keep route-level requests in pages, reusable presentation in `components/`,
   session-wide state in Pinia, and backend transport in `api/client.js`.
3. Reuse the visual language: forest green, warm paper, coral accents,
   editorial headings, compact evidence cards, and restrained motion.
4. Provide loading, empty, disabled, and failure-safe states. Forms must have
   labels, useful placeholders, native validation, and no duplicate submission.
5. Verify desktop and mobile widths. Navigation, inputs, uploads, chat, and
   interview actions must remain keyboard and touch usable.
6. Add focused Vitest coverage. Run `npm test`, then `npm run build`.

Return owned paths, behavior changes, API assumptions, and exact check results.
Do not self-approve completion.
