// Mirror of backend myrtia/events/schema.py — the live-view contract.

export type EventType =
  | "run.started"
  | "run.finished"
  | "goal.started"
  | "turn.started"
  | "proposal.created"
  | "critique.created"
  | "vote.aggregated"
  | "chairman.synthesized"
  | "target.responded"
  | "judge.scored"
  | "approval.requested"
  | "approval.resolved"
  | "log";

export interface RunEvent {
  id: string;
  run_id: string;
  type: EventType;
  seq: number;
  ts: number;
  payload: Record<string, unknown>;
}

export interface LaunchSpec {
  attack_id: string;
  attack_config: Record<string, unknown>;
  target: { kind: string; base_url: string; model: string; api_key?: string };
  goals: string[];
}
