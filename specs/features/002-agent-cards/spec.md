# Spec 002 — Agent cards on the canvas

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Implemented
- **Issue:** to be created

## Context and goal

On the graph builder, an agent node shows a role label, a model and one truncated line
about its prompt. What the agent actually carries (a custom prompt, attack tools,
few-shot priming) is hidden behind a dialog, tools appear only as numbered bubbles, and
every agent is called "Attacker N", so two agents with different jobs look the same.
Adding an agent is a global button, unrelated to the agent the operator is looking at.

This feature turns each agent node into a card that states what the agent is and what it
carries, and lets the operator change those parts and add agents from the card itself.
The goal is that an attack design can be read from the canvas without opening anything.

## Users

- **Red-teamer designing an attack** — wants to see at a glance what each agent does
  and adjust it in place.
- **Reviewer reading someone else's design** — wants to understand the roles in the
  graph without clicking through every node.

## User stories

- **US-1** — As a red-teamer, I want to give an agent a name and a short description,
  so that the graph explains itself.
- **US-2** — As a red-teamer, I want each card to list what the agent carries, so that
  I can tell agents apart without opening them.
- **US-3** — As a red-teamer, I want to remove or open a part from its row on the card,
  so that small changes take one click.
- **US-4** — As a red-teamer, I want to add a part, or a new attacker, from the card I
  am looking at, so that I do not leave the place I am working in.

## Terms

- **Agent**: an attacker or a chairman node. The target and the evaluator are not
  agents in this spec and keep their current look.
- **Part**: something an agent carries. An agent always has a **prompt** part (the
  default prompt or a custom one). An attacker may also have **attack tool** parts and
  one **few-shot priming** part.

## Functional requirements

### What a card shows

- **FR-1** — THE SYSTEM SHALL show on each agent card the agent's name, its model and a
  summary of what it carries: whether its prompt is the default or a custom one, how
  many attack tools it has, and whether it has few-shot priming.
- **FR-2** — WHILE an agent has no name of its own, THE SYSTEM SHALL show its default
  label (for example "Attacker 2" or "Chairman") as its name.
- **FR-27** — WHEN the operator points at a card, moves keyboard focus into it or
  selects it, THE SYSTEM SHALL open the card's detail: the agent's description, if it
  has one, and one row per part it carries.
- **FR-3** — WHERE an agent has a description, THE SYSTEM SHALL show the description in
  the card's detail.
- **FR-4** — THE SYSTEM SHALL label the prompt, in the summary and in its row, so that a
  default prompt and a custom prompt can be told apart.
- **FR-25** — THE SYSTEM SHALL keep every agent card the same size whatever the agent
  carries, so that a card needs no more room on the canvas than a node did. The detail
  opens over the canvas without moving other nodes.
- **FR-26** — WHEN the operator points at a card or moves keyboard focus into it, THE
  SYSTEM SHALL bring that card in front of the cards that overlap it.
- **FR-6** — THE SYSTEM SHALL show names and descriptions as plain text, so that markup
  typed into them is displayed and never interpreted.

### Naming

- **FR-7** — WHEN the operator edits an agent, THE SYSTEM SHALL let them set its name
  (up to 40 characters) and its description (up to 140 characters).
- **FR-8** — WHEN the operator clears an agent's name, THE SYSTEM SHALL return to the
  default label.
- **FR-9** — THE SYSTEM SHALL keep names and descriptions with the graph: they survive
  reloading the page and are restored by undo and redo and by saved presets.

### Changing parts from the card

- **FR-10** — WHEN the operator activates a part row, THE SYSTEM SHALL open the editor
  for that part.
- **FR-11** — WHEN the operator removes an attack tool row, THE SYSTEM SHALL take that
  tool away from the agent.
- **FR-12** — WHEN the operator removes a custom prompt row, THE SYSTEM SHALL return the
  agent to the default prompt.
- **FR-13** — WHEN the operator removes the few-shot priming row, THE SYSTEM SHALL
  return the agent to a single prompt with no priming.
- **FR-14** — THE SYSTEM SHALL offer no remove control on a default prompt row.
- **FR-15** — WHEN the operator activates a card's add control, THE SYSTEM SHALL offer
  the parts that agent can still take: a custom prompt (while it uses the default),
  attack tools and few-shot priming (attackers only, priming only while it has none).
- **FR-16** — THE SYSTEM SHALL record every change made from a card so that undo
  reverses it.

### Adding an attacker from a card

- **FR-17** — THE SYSTEM SHALL offer "New attacker" in the add control of every agent
  card.
- **FR-18** — WHEN the operator chooses "New attacker", THE SYSTEM SHALL ask for a name
  (optional), a model (pre-filled with the model of the agent it was opened from) and a
  description (optional).
- **FR-19** — WHEN the operator confirms, THE SYSTEM SHALL add an attacker with those
  values to the canvas.
- **FR-20** — WHEN the operator cancels, THE SYSTEM SHALL change nothing.
- **FR-21** — IF the canvas already has the maximum number of attackers, THEN THE
  SYSTEM SHALL say so and add nothing.

### What stays the same

- **FR-22** — THE SYSTEM SHALL keep the existing ways of working: activating the card
  itself opens the agent editor, the remove control deletes the agent, and the toolbar
  still adds attackers.
- **FR-23** — THE SYSTEM SHALL send the same run request as before for the same graph:
  names and descriptions are not part of it.
- **FR-24** — THE SYSTEM SHALL draw each connection so that it meets the edge of the
  card, whatever the card's height.

## Non-functional requirements

- **NFR-1** — Every control on a card can be reached and activated with the keyboard
  and has an accessible name.
- **NFR-2** — Cards are legible in the dark and the light theme.
- **NFR-3** — In every topology, with two to five attackers, the cards overlap no more
  than the nodes did before this feature. Layouts are not changed here; the ring already
  overlapped neighbours at seven and eight attackers.
- **NFR-4** — The UI stays a single file with no build step.

## Edge cases

- A name or description made only of spaces counts as empty.
- A name longer than the card is shortened with an ellipsis; the full name is available
  on hover and in the editor.
- A graph saved before this feature (agents without names) loads unchanged.
- The last remaining attacker can lose parts but cannot be deleted, as today.
- A chairman has only a prompt part; its add control offers a custom prompt and
  "New attacker", nothing else.
- Removing a tool also discards that tool's settings, as the editor does today.

## Out of scope

- Sending names or descriptions to the backend, or showing them in the live view,
  history or reports.
- Names for the target and the evaluator.
- Nesting agents under other agents; topologies are unchanged.
- Reordering parts or agents by drag and drop.
- A new prompt editor: the existing agent editor is reused.

## Acceptance scenarios

```gherkin
Feature: Agent cards

  Scenario: A default agent shows its default prompt               # FR-1, FR-2, FR-4, FR-14
    Given the Myrtia console is open
    Then the card of attacker 1 is named "Attacker 1"
    And the card of attacker 1 lists the part "Default prompt"
    And the part "Default prompt" of attacker 1 cannot be removed

  Scenario: Naming and describing an agent                         # FR-3, FR-7, FR-9
    Given the Myrtia console is open
    When I name attacker 1 "Persuader" with the description "Builds rapport first"
    Then the card of attacker 1 is named "Persuader"
    And the card of attacker 1 shows the description "Builds rapport first"
    When I reload the page
    Then the card of attacker 1 is named "Persuader"

  Scenario: Clearing a name returns to the default label           # FR-8
    Given the Myrtia console is open
    And attacker 1 is named "Persuader"
    When I clear the name of attacker 1
    Then the card of attacker 1 is named "Attacker 1"

  Scenario: Markup in a name is shown as text                      # FR-6
    Given the Myrtia console is open
    When I name attacker 1 "<img src=x onerror=alert(1)>" with the description "<b>bold</b>"
    Then the card of attacker 1 is named "<img src=x onerror=alert(1)>"
    And the card of attacker 1 contains no injected element

  Scenario: Adding a tool from the card                            # FR-15, FR-1
    Given the Myrtia console is open
    When I add the attack tool "obfuscation" from the card of attacker 1
    Then the card of attacker 1 lists the part "obfuscation"

  Scenario: Removing a tool from its row                           # FR-11
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    When I remove the part "obfuscation" from the card of attacker 1
    Then the card of attacker 1 does not list the part "obfuscation"

  Scenario: Undo restores a removed tool                           # FR-16
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    When I remove the part "obfuscation" from the card of attacker 1
    And I undo
    Then the card of attacker 1 lists the part "obfuscation"

  Scenario: A custom prompt can be removed from the card           # FR-4, FR-12
    Given the Myrtia console is open
    And attacker 1 has the custom prompt "You are a patient negotiator."
    Then the card of attacker 1 lists the part "Custom prompt"
    When I remove the part "Custom prompt" from the card of attacker 1
    Then the card of attacker 1 lists the part "Default prompt"

  Scenario: Priming added and removed from the card                # FR-13, FR-15
    Given the Myrtia console is open
    When I add few-shot priming from the card of attacker 1
    Then the card of attacker 1 lists the part "Few-shot priming"
    When I remove the part "Few-shot priming" from the card of attacker 1
    Then the card of attacker 1 does not list the part "Few-shot priming"

  Scenario: Opening a part from its row                            # FR-10
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    When I open the part "obfuscation" on the card of attacker 1
    Then the settings of the tool "obfuscation" are shown

  Scenario: The summary counts the attack tools                    # FR-1
    Given the Myrtia console is open
    And attacker 1 has 5 attack tools
    Then the summary of attacker 1 shows 5 attack tools
    And the summary of attacker 2 shows no attack tools

  Scenario: The detail opens when the card is pointed at           # FR-27
    Given the Myrtia console is open
    Then the detail of attacker 1 is hidden
    When I point at the card of attacker 1
    Then the detail of attacker 1 is shown

  Scenario: A card keeps the size of a node whatever it carries    # FR-25
    Given the Myrtia console is open
    And attacker 1 has 5 attack tools
    And attacker 1 is named "Persuader"
    Then the card of attacker 1 is the same size as the card of attacker 2

  Scenario: An overlapped card comes to the front                  # FR-26
    Given the Myrtia console is open
    And the canvas has 8 attackers
    When I point at the overlapped card of attacker 2
    Then no other card covers the controls of attacker 2

  Scenario: A new attacker from a card                             # FR-17, FR-18, FR-19
    Given the Myrtia console is open
    And attacker 1 uses the model "special-model"
    When I choose "New attacker" on the card of attacker 1
    Then the new attacker form proposes the model "special-model"
    When I confirm the new attacker as "Closer" described as "Asks for the final answer"
    Then the canvas shows 4 attacker nodes
    And the card of attacker 4 is named "Closer"
    And the card of attacker 4 shows the description "Asks for the final answer"

  Scenario: Cancelling a new attacker changes nothing              # FR-20
    Given the Myrtia console is open
    When I choose "New attacker" on the card of attacker 1
    And I cancel the new attacker form
    Then the canvas shows 3 attacker nodes

  Scenario: The attacker limit is respected                        # FR-21
    Given the Myrtia console is open
    And the canvas has 8 attackers
    When I choose "New attacker" on the card of attacker 1
    Then I am told the attacker limit is reached
    And the canvas shows 8 attacker nodes

  Scenario: A chairman offers only what it can take                # FR-15, FR-17
    Given the Myrtia console is open
    And I have chosen the "Chairman" topology
    When I open the add control on the chairman card
    Then the add control offers exactly "Custom prompt" and "New attacker"

  Scenario: Names are not part of the run request                  # FR-23
    Given the Myrtia console is open
    And attacker 1 is named "Persuader"
    Then the run request for the graph contains no name or description

  Scenario: Connections meet the card whatever its height          # FR-24
    Given the Myrtia console is open
    And attacker 1 has 3 attack tools
    Then the height used to draw the connections of attacker 1 matches its card

  Scenario: Cards can be used with the keyboard                    # NFR-1
    Given the Myrtia console is open
    And attacker 1 has the attack tool "obfuscation"
    Then every control on the card of attacker 1 is a button with an accessible name
```

The existing builder scenarios of spec 001 (open, add, remove, edit model, change
topology, live run) keep passing unchanged (FR-22).

Manual checks:

- Light and dark theme: cards and rows are legible (NFR-2).
- Every topology with two to five attackers, at two window widths: a scripted
  comparison with the page before this feature finds no additional overlap (NFR-3).

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend`, `pytest -m "not e2e"` and the UI scenarios pass.
3. The two manual checks are recorded with screenshots in the pull request.

## Decisions from clarification

Taken by the implementer under a standing instruction to proceed without questions;
each is a default the maintainer can change:

- The target and the evaluator keep their current look.
- Names and descriptions stay in the canvas and are not sent with the run.
- "Adding an agent from a card" means adding an attacker; no nesting is introduced.
- The numbered tool bubbles and the separate tools button on the node are replaced by
  the part rows and the card's add control.
- A card keeps the footprint of a node and its detail opens on pointing, focus or
  selection. Showing every row on the card at all times was built first and rejected:
  cards up to 220 px tall overlapped or left the canvas in the pipeline, parallel and
  mixture-of-agents layouts, and above three agents in the ring.

## Open questions

None.
