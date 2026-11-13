# Tasks NNN — <feature name>

> Small tasks (about 20–30 minutes each) in dependency order. Implement one at a time,
> test first: write the failing scenario or unit test, make it pass with the minimum
> code, refactor, run the checks, tick the box, stop.

- [ ] **T1 — Write the acceptance scenarios** (FR-1 … FR-n)
  Add `backend/tests/features/<name>.feature` from the spec, with step stubs.
  Done when: the scenarios are collected by pytest and fail for the right reason.

- [ ] **T2 — <short title>** (FR-2, FR-3)
  <What to do.>
  Done when: <a check that can be run or observed>.

- [ ] **T<last> — Validate the spec**
  Walk `spec.md` requirement by requirement, state what proves each one, and check the
  acceptance criteria.
  Done when: every requirement is covered and the verdict is written in the pull request.
