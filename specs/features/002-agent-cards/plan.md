# Plan 002 — Agent cards on the canvas

> How the spec will be built. Read `specs/constitution/` and this feature's `spec.md`
> first. Every part names the requirements it covers.

## Approach

All changes are in `frontend/standalone.html`, inside the existing graph builder code.
The node renderer builds attacker and chairman nodes as cards with the footprint of a
node: a tinted header band with the name and an add control, the model, and a row of
summary chips (prompt, number of tools, priming). The card's detail, with the
description and one row per part, is an absolutely positioned child that opens over the
canvas on hover, keyboard focus or selection, below the card or above it for cards in
the lower half of the canvas. No layout has to make room for it.

Rows and the add control call the editors that already exist (agent editor, tool
picker, tool settings). Two new fields, `name` and `desc`, live on the agent objects of
the canvas state, which is already what is saved, restored by undo and stored in
presets. The run request builder is not touched, so names never leave the browser.

Connections are clipped at each card's measured size instead of a fixed node size.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| Node styles (`.gnode …`) | Card styles: header band, add control, summary chips, detail with description and part rows | FR-1 … FR-4, NFR-2 |
| `renderGraph()` → `mk()` | Agent nodes rendered as cards; inner controls do not start a drag or open the editor | FR-1 … FR-6, FR-22 |
| `gAttachTools()` | Replaced by `gCardParts()` (rows) and the add control | FR-1, FR-10 … FR-15 |
| New `gAgentParts()`, `gCardSummary()`, `gAgentName()` | Pure helpers that derive what a card shows from the agent | FR-1, FR-2, FR-4 |
| New `openAddMenu()`, `openNewAttacker()` | The add control's menu and the new attacker form, in the existing floating panel | FR-15, FR-17 … FR-21 |
| `openGDialog()` | Name and description fields; optional field to focus; live updates look the node up instead of holding a reference | FR-7, FR-8, FR-10 |
| `openToolPicker()` | Records an undo checkpoint when a tool is toggled | FR-16 |
| `gClip()` and the feedback connection | Use the agent's measured half-height when present | FR-24 |
| Node styles | The detail opens on hover, focus or selection; that card is stacked above its neighbours | FR-25, FR-26, FR-27 |
| `gFloatPos()` | Floating panels are clamped with their real height and scroll if taller than the window, so their buttons stay on screen | FR-10, FR-15 |
| `backend/tests_ui/features/agent_cards.feature`, `test_agent_cards.py` | The acceptance scenarios | all |
| `backend/tests_ui/conftest.py`, `test_builder.py` | Steps shared by both features moved to `conftest.py` | FR-22 |

`graphBody()`, the backend and the event stream are unchanged (FR-23).

## Data and state

```js
// an attacker in GS.attackers (a chairman has the same two new fields)
{ id: "a1", model: "qwen2.5:3b", system: "", endpoint: "",
  tools: ["obfuscation"], tool_cfg: {}, priming: { mode: "single", context: "" },
  name: "Persuader",            // new, optional, at most 40 characters
  desc: "Builds rapport first"  // new, optional, at most 140 characters
}
```

- Absent or blank `name` means the default label; absent `desc` means no description
  line. Graphs saved earlier therefore load unchanged.
- `G_CARD_HY`, `G_CARD_HX`: maps from node id to the half-height and half-width last
  measured for that card. They are not saved; they are refreshed on every render.

## Contracts

Parts of an agent, in display order (`gAgentParts(kind, agent)`):

| Type | Key | Label | Removable | Open | Remove |
|---|---|---|---|---|---|
| `prompt` | `prompt` | `Default prompt` or `Custom prompt` | only when custom | agent editor, prompt focused | `system = ""` |
| `tool` | the tool id | the tool id | yes | tool settings | drop from `tools` and `tool_cfg` |
| `priming` | `priming` | `Few-shot priming` | yes | agent editor, priming focused | `priming.mode = "single"` |

Summary chips, in order: the prompt (`Default` or `Custom`), the tools (their number,
only when there are any) and priming (an icon, only when set). Each chip's tooltip
states it in full.

Markup of a card (selectors used by the scenarios):

```html
<div class="gnode attacker card" data-id="a1">        <!-- "up" is added in the lower half -->
  <div class="gr"><i></i><span class="gname" title="Persuader — Builds rapport first">Persuader</span>
    <button class="gadd" aria-label="Add to Persuader">+</button></div>
  <div class="gbody">
    <div class="gm"><svg/><span>qwen2.5:3b</span></div>
    <div class="gsum">
      <span class="gchip" data-type="prompt" title="Default prompt"><svg/><span>Default</span></span>
      <span class="gchip" data-type="tool" title="1 attack tool: obfuscation"><svg/><span>1</span></span>
    </div>
  </div>
  <div class="gdetail">                              <!-- hidden until hover, focus or selection -->
    <div class="gdesc">Builds rapport first</div>
    <div class="gcarries">Carries</div>
    <div class="gparts">
      <div class="gpart" data-type="tool" data-part="obfuscation">
        <button class="gpart-open" aria-label="Open obfuscation"><svg/><span>obfuscation</span></button>
        <button class="gpart-rm" aria-label="Remove obfuscation">×</button>
      </div>
    </div>
  </div>
  <button class="gx" aria-label="Remove Persuader">×</button>
</div>
```

Add menu items carry `data-add="prompt" | "tools" | "priming" | "attacker"`. The new
attacker form uses `#ga_name`, `#ga_model`, `#ga_desc`, `#ga_create`, `#ga_cancel`.

## UI behaviour

- Clicking a card outside its controls opens the agent editor, as today.
- Controls inside a card stop the click from reaching the card and do not start a drag.
- Removing a part records an undo checkpoint, saves and re-renders. If the agent editor
  is open on that agent it is closed, so it cannot show stale values.
- Name and description are edited in the agent editor; the card updates as they are
  typed. Names are shown through `textContent` or the existing `esc()` helper.
- The attacker limit (eight) is checked when "New attacker" is chosen: at the limit a
  message is shown and the form does not open.

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Rows reuse the existing editors | Smallest change; one place to edit each thing | A new inline editor per row: more code and two ways to edit the same value |
| Measure card height after render and re-render once if it changed | Exact for any font and theme; web fonts change text height | Predicting height from constants: breaks when the font fails to load |
| Half-height carried on the position object (`pos[id].hy`) | `gClip()` already receives that object; no call site changes | Passing ids through thirteen `gLine()` call sites |
| Replace the tool bubbles and the tools button | The rows and the add control do the same job more legibly; two affordances for one action confuse | Keeping both: clutter on a 170 px card |
| Names stay client-side | The spec keeps the run request unchanged; the trace feature will decide how agents are identified in events | Sending `name` now: a backend contract with no consumer yet |
| Card with the footprint of a node; detail on hover, focus or selection | Every topology's layout keeps working unchanged, and the canvas stays readable at a glance | Always-visible rows: built first, cards up to 220 px tall overlapped or left the canvas in pipeline, parallel and mixture-of-agents, and above three agents in the ring. Making every layout size-aware is a larger change |
| Detail opens upward in the lower half of the canvas | The canvas clips its content, so a detail opening downward from a low card would be cut | Letting the canvas overflow: it would cover the form below |
| Raise the card that is pointed at or focused | The ring already overlapped neighbours at seven and eight attackers, hiding one node's remove control; this makes every control reachable without touching the layout | Widening the ring: it collides with the target on narrow canvases |
| Fix the floating panel position | The tool picker is taller than the 280 px the old clamp assumed, so on an 800 px window its Done button was off screen and unreachable | Leaving it: the scenarios, and operators on small screens, could not confirm the picker |

## Constitution check

- **Zero-build frontend (2):** plain HTML, CSS and JavaScript in the single file.
- **Secrets (6):** no new field holds a secret; names and descriptions are free text
  shown as text only (FR-6).
- **Test-driven (11):** the scenarios in `agent_cards.feature` are written and seen
  failing before the page is changed.
- **Traceable by default (12):** no run behaviour changes, so no event changes.
- **Small, focused changes (10):** one file of product code.

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1, FR-2, FR-4, FR-14 | "A default agent shows its default prompt", "The summary counts the attack tools" |
| FR-3, FR-7, FR-9 | "Naming and describing an agent" |
| FR-8 | "Clearing a name returns to the default label" |
| FR-6 | "Markup in a name is shown as text" |
| FR-15 | "Adding a tool from the card", "Priming added and removed from the card", "A chairman offers only what it can take" |
| FR-11 | "Removing a tool from its row" |
| FR-16 | "Undo restores a removed tool" |
| FR-12 | "A custom prompt can be removed from the card" |
| FR-13 | "Priming added and removed from the card" |
| FR-10 | "Opening a part from its row" |
| FR-17 … FR-19 | "A new attacker from a card" |
| FR-20 | "Cancelling a new attacker changes nothing" |
| FR-21 | "The attacker limit is respected" |
| FR-22 | The six scenarios of `builder.feature` still pass |
| FR-23 | "Names are not part of the run request" |
| FR-24 | "Connections meet the card whatever its height" |
| NFR-1 | "Cards can be used with the keyboard" |
| FR-25 | "A card keeps the size of a node whatever it carries" |
| FR-27 | "The detail opens when the card is pointed at" |
| FR-26 | "An overlapped card comes to the front" |
| NFR-2 | Manual, with screenshots of the collapsed and the open card in both themes |
| NFR-3 | Scripted: every topology at two to five attackers and two window widths, compared with the page before this feature (48 cases) |

## Risks

- **Re-render loop when measuring.** The second render only happens when a measured
  height differs from the stored one by more than a pixel, and at most once per render.
- **Stale references in the agent editor.** Live updates look the node up by id each
  time, because rows cause re-renders while the editor is open.
- **Dense graphs.** Cards have the footprint of a node, so layouts behave as before. At
  seven and eight attackers the ring still overlaps two neighbours, as it did; the
  overlapped card comes to the front when pointed at or focused. A layout that leaves
  room is in the backlog.
- **Hover-only detail on touch screens.** The detail also opens on focus and when the
  card is selected, and everything in it is available in the agent editor.
- **Existing scenarios depend on node markup.** `.gnode`, `.gm`, `.gx`, `.gr` and
  `data-id` are kept; the 001 scenarios run on every change.
