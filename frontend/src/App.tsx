import { useState } from "react";
import { launchRun } from "./api";
import { useRunStream } from "./useRunStream";
import type { LaunchSpec, RunEvent } from "./types";

function panelClass(type: string): string {
  const key = type.split(".")[0];
  return `ev ev-${key}`;
}

function eventBody(ev: RunEvent): string {
  const p = ev.payload as Record<string, any>;
  switch (ev.type) {
    case "proposal.created":
      return `${p.model ?? "?"} · mutator=${p.mutator ?? "?"}\n${p.proposal ?? ""}`;
    case "critique.created":
      return `${p.critic ?? "?"} ranks ${JSON.stringify(p.rankings ?? [])}`;
    case "vote.aggregated":
      return `winner: ${p.winner ?? "?"}  borda=${JSON.stringify(p.borda_scores ?? {})}`;
    case "chairman.synthesized":
      return String(p.synthesized_prompt ?? "");
    case "target.responded":
      return String(p.target_response ?? "").slice(0, 800);
    case "judge.scored":
      return `score ${p.score}/5  ${p.rationale ?? ""}`;
    default:
      return JSON.stringify(p);
  }
}

export function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const { events, connected } = useRunStream(runId);
  const [form, setForm] = useState({
    attack: "council",
    turl: "http://127.0.0.1:11434/v1",
    tmodel: "gpt-oss:120b",
    cmodels: "gemma3:12b",
    goal: "<behaviour to test>",
  });

  async function launch() {
    const spec: LaunchSpec = {
      attack_id: form.attack.trim(),
      attack_config: {
        council_models: form.cmodels.split(",").map((s) => s.trim()).filter(Boolean),
        use_borda: true,
        use_chairman: true,
      },
      target: { kind: "openai_chat", base_url: form.turl.trim(), model: form.tmodel.trim() },
      goals: [form.goal],
    };
    setRunId(await launchRun(spec));
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <header>
        <h1>Myrtia <small>— live deliberation</small></h1>
        <span className="badge">{connected ? "connected" : "disconnected"}</span>
        <span className="badge">{runId ?? "no run"}</span>
      </header>
      <main>
        <section className="card">
          <strong>Launch a run</strong>
          <label>Attack plugin id</label>
          <input value={form.attack} onChange={set("attack")} />
          <label>Target base_url (OpenAI-compat)</label>
          <input value={form.turl} onChange={set("turl")} />
          <label>Target model</label>
          <input value={form.tmodel} onChange={set("tmodel")} />
          <label>Council models (comma-sep)</label>
          <input value={form.cmodels} onChange={set("cmodels")} />
          <label>Goal / behaviour</label>
          <textarea rows={2} value={form.goal} onChange={set("goal")} />
          <button onClick={launch}>Launch</button>
        </section>
        <section id="stream">
          {events.map((ev) => (
            <div key={ev.id} className={panelClass(ev.type)}>
              <div className="t">#{ev.seq} {ev.type}</div>
              <pre>{eventBody(ev)}</pre>
            </div>
          ))}
        </section>
      </main>
    </>
  );
}
