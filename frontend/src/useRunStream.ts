import { useCallback, useEffect, useRef, useState } from "react";
import { connectRunStream } from "./api";
import type { RunEvent } from "./types";

// Subscribes to a run's WebSocket and accumulates ordered, de-duplicated events.
export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const seen = useRef<Set<string>>(new Set());

  const reset = useCallback(() => {
    seen.current = new Set();
    setEvents([]);
  }, []);

  useEffect(() => {
    if (!runId) return;
    reset();
    const ws = connectRunStream(runId, (ev) => {
      if (seen.current.has(ev.id)) return;
      seen.current.add(ev.id);
      setEvents((prev) => [...prev, ev].sort((a, b) => a.seq - b.seq));
    });
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    return () => ws.close();
  }, [runId, reset]);

  return { events, connected };
}
