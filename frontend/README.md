# Myrtia frontend

React 19 + Vite + TypeScript UI that renders an attack run's deliberation live from
the backend's per-run WebSocket. Follows the patterns in `../docs/ui-observability-map.md`
(event-panel stream); the heavier GraphQL/Apollo path is deferred to Phase 4.

## Two ways to run

**Zero-build (right now):** open `standalone.html` in a browser with the backend
running. It POSTs a run and connects to the WebSocket — no install, no build step.
Good for a quick end-to-end demo.

**Dev app:** the real Vite scaffold (install deferred, like ARES on the backend):

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /runs + WS to backend :8000
```

## Source

- `src/types.ts` — mirror of the backend event schema (the live-view contract)
- `src/api.ts` — launch a run + open the run WebSocket
- `src/useRunStream.ts` — hook: ordered, de-duplicated event accumulation
- `src/App.tsx` — launch form + live deliberation panels (proposal/critique/vote/
  chairman/target/judge)

## Next

- Approval prompt UI wired to `POST /approvals/{id}` (HITL gate)
- Group events by goal/turn; token streaming for proposals
- Migrate to the design system (Tailwind/shadcn) once the flow stabilises
