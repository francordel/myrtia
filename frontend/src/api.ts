import type { LaunchSpec, RunEvent } from "./types";

// Relative paths go through the Vite dev proxy to the Python backend.
export async function launchRun(spec: LaunchSpec): Promise<string> {
  const res = await fetch("/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!res.ok) throw new Error(`launch failed: ${res.status}`);
  const data = (await res.json()) as { run_id: string };
  return data.run_id;
}

export function streamUrl(runId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/runs/${runId}/events`;
}

export type EventHandler = (ev: RunEvent) => void;

export function connectRunStream(runId: string, onEvent: EventHandler): WebSocket {
  const ws = new WebSocket(streamUrl(runId));
  ws.onmessage = (m) => onEvent(JSON.parse(m.data) as RunEvent);
  return ws;
}
