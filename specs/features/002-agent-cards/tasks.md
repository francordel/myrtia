# Tasks 002 — Agent cards on the canvas

> Small tasks (about 20–30 minutes each) in dependency order. Implement one at a time,
> test first: write the failing scenario or unit test, make it pass with the minimum
> code, refactor, run the checks, tick the box, stop.
>
> Notes from implementation: the eighteen scenarios of T1 were run and seen failing
> before any product code existed. The first design drew every row on the card. The
> manual check of T9, run across all topologies, showed those cards did not fit the
> existing layouts, so the design changed to a card with the footprint of a node whose
> detail opens on pointing, focus or selection (FR-25, FR-27), and FR-26 was added for
> overlapped cards. Their scenarios were written together with their code, not before
> it. T9 also found that the tool picker's Done button fell off screen on an 800 px
> window, fixed in the floating panel position. T10's verdict goes in the pull request;
> nothing is committed by the implementer.

- [x] **T1 — Write the acceptance scenarios** (FR-1 … FR-24, NFR-1)
  Add `backend/tests_ui/features/agent_cards.feature` from the spec and
  `test_agent_cards.py` with its steps. Move the steps shared with `test_builder.py`
  into `conftest.py`.
  Done when: the scenarios are collected and fail because the cards do not exist yet,
  and the six builder scenarios still pass.

- [x] **T2 — Card structure and part rows** (FR-1, FR-2, FR-4, FR-14, FR-22, FR-25, FR-27)
  Add `gAgentName()`, `gAgentParts()` and `gCardSummary()`; render attacker and chairman
  nodes as cards with a name, model, summary chips and a detail with the part rows; add
  the card styles.
  Done when: "A default agent shows its default prompt" and "The summary counts the
  attack tools" pass, and the builder scenarios still pass.

- [x] **T3 — Name and description** (FR-3, FR-6, FR-7, FR-8, FR-9)
  Add the two fields to the agent editor, with their length limits, and show them on
  the card as plain text.
  Done when: the naming, clearing and markup scenarios pass.

- [x] **T4 — Open and remove parts from their rows** (FR-10 … FR-13, FR-16)
  Wire each row's open and remove controls; record an undo checkpoint on removal and on
  tool toggles in the picker.
  Done when: the tool removal, undo, custom prompt, priming removal and open-a-part
  scenarios pass.

- [x] **T5 — Add control and its menu** (FR-15)
  Add the card's add control and the menu of parts the agent can still take; remove the
  tool bubbles and the separate tools button.
  Done when: "Adding a tool from the card", the priming scenario and the chairman
  scenario pass.

- [x] **T6 — New attacker from a card** (FR-17 … FR-21)
  Add the "New attacker" form, pre-filled with the model of the agent it was opened
  from, and the limit check.
  Done when: the new attacker, cancel and limit scenarios pass.

- [x] **T7 — Connections follow the card height** (FR-24)
  Measure each card after rendering, keep its half-height, and use it when clipping
  connections and the feedback connection.
  Done when: "Connections meet the card whatever its height" passes.

- [x] **T8 — Keyboard and run request** (FR-23, NFR-1)
  Give every control on a card a button role and an accessible name.
  Done when: the keyboard scenario and "Names are not part of the run request" pass.

- [x] **T9 — Manual checks and full verification** (NFR-2, NFR-3, NFR-4)
  Capture the collapsed and the open card in the dark and the light theme. Compare
  overlaps in every topology with the page before this feature. Run lint, the offline
  suite and the whole UI tier.
  Done when: no additional overlap is found and all checks pass.

- [x] **T10 — Validate the spec** (all)
  Walk `spec.md` requirement by requirement and state what proves each one. Mark the
  feature in `roadmap.md`.
  Done when: every requirement is covered and the verdict is written in the pull
  request.
