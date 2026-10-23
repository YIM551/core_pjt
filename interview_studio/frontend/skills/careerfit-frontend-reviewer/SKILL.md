---
name: careerfit-frontend-reviewer
description: Independently review CareerFit frontend diffs for API-contract, session, async-state, accessibility, responsive, and UX defects. This skill is read-only.
---

# CareerFit Frontend Reviewer

Do not edit files, install packages, run formatters, or update snapshots.

1. Read the supplied diff, owned production paths, matching backend routes, and
   focused tests.
2. Report each finding with severity, path, line, consequence, and smallest fix.
3. Mark each item pass, finding, or not applicable: route/API envelope;
   HttpOnly session; personal/company scope; loading/empty/error/success and
   duplicate-submit states; labels/keyboard/focus/contrast; mobile overflow and
   touch targets; unsafe rendering or sensitive persistence; focused tests and
   production build.
4. End with `0 findings` only when no issue remains.
