"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { STEP_ORDER } from "./format";
import type { RunEvent, Step } from "./types";

export function useMissionEvents(id: string) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [ended, setEnded] = useState(false);
  const [connection, setConnection] = useState<"connecting" | "open" | "lost">("connecting");

  useEffect(() => {
    const seen = new Set<number>(); // EventSource reconnects replay from 0: dedupe by sequence number
    const es = new EventSource(api.eventsUrl(id));
    es.onopen = () => setConnection("open");
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data) as RunEvent;
      if (ev.seq !== undefined) { if (seen.has(ev.seq)) return; seen.add(ev.seq); }
      setEvents((p) => [...p, ev]);
      if (ev.type === "end") { setEnded(true); es.close(); }
    };
    es.onerror = () => setConnection(es.readyState === EventSource.CLOSED ? "lost" : "connecting");
    return () => es.close();
  }, [id]);

  const derived = useMemo(() => {
    const steps: Record<string, { status: Step["status"]; note: string | null }> = {};
    STEP_ORDER.forEach((s) => (steps[s] = { status: "pending", note: null }));
    let credits = 0, finalState: string | undefined, error: string | undefined, running = false;
    const calls: RunEvent[] = [];
    const log: RunEvent[] = [];
    for (const e of events) {
      if (e.type === "status") {
        if (e.status === "running") running = true;
        if (e.state) finalState = e.state;
        if (e.error) error = e.error;
      } else if (e.type === "event") {
        if (e.step === "tool") { calls.push(e); credits += e.credit ?? 0; continue; }
        log.push(e);
        if (e.step && steps[e.step]) {
          if (e.msg === "started") steps[e.step].status = "running";
          else if (["done", "warning", "failed", "skipped"].includes(e.msg ?? "")) {
            steps[e.step].status = e.msg as Step["status"]; steps[e.step].note = e.warning ?? null;
          }
        }
      }
    }
    return { steps, credits, calls, log, finalState, error, running };
  }, [events]);

  return { events, ended, connection, ...derived };
}
