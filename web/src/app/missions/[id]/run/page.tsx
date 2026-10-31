"use client";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle2, CircleDashed, Loader2, MinusCircle, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, Callout, Card, CardHeader, Meter } from "@/components/ui";
import { api } from "@/lib/api";
import { STATE_LABEL, STEP_LABEL, STEP_ORDER } from "@/lib/format";
import { useMissionEvents } from "@/lib/use-events";

const ICON = {
  pending: <CircleDashed size={18} className="text-muted" />, running: <Loader2 size={18} className="animate-spin text-brand" />,
  done: <CheckCircle2 size={18} className="text-good" />, warning: <AlertTriangle size={18} className="text-warn" />,
  failed: <XCircle size={18} className="text-bad" />, skipped: <MinusCircle size={18} className="text-muted" />,
} as const;

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const status = useQuery({ queryKey: ["status", id], queryFn: () => api.status(id), retry: false });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const { ended, connection, steps, credits, calls, log, finalState, error } = useMissionEvents(id);
  const [elapsed, setElapsed] = useState(0);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (ended) return; const t = setInterval(() => setElapsed((s) => s + 1), 1000); return () => clearInterval(t); }, [ended]);
  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight }); }, [log.length, calls.length]);
  useEffect(() => { if (ended && !error) { const t = setTimeout(() => router.replace(`/missions/${id}`), 1800); return () => clearTimeout(t); } }, [ended, error, id, router]);

  if (status.error) return <Callout tone="bad" title="Mission not found">It may have been deleted, or the server restarted while it was running. <Link className="underline" href="/">Start a new mission</Link>.</Callout>;
  const cap = settings.data?.caps.max_credits_per_mission ?? 400;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{ended ? (error ? "Mission failed" : "Mission finished") : "Running your mission"}</h1>
          <p className="text-sm text-muted">No input needed. This page updates live.{!ended && ` Elapsed ${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`}</p>
        </div>
        <div className="flex items-center gap-2">
          {connection === "lost" && !ended && <Badge tone="warn">connection lost: reload to resume</Badge>}
          {ended && <Link href={`/missions/${id}`}><Button data-testid="open-results">Open results <ArrowRight size={16} /></Button></Link>}
        </div>
      </div>

      {error && <div className="mb-4"><Callout tone="bad" title="The mission stopped unexpectedly">{error}</Callout></div>}
      {ended && finalState && !error && <div className="mb-4"><Callout tone={finalState === "failed" ? "bad" : finalState === "completed" ? "good" : "warn"} title={STATE_LABEL[finalState] ?? finalState}>Redirecting to your results… partial results and every warning are preserved.</Callout></div>}

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Progress" right={<Badge tone="neutral">{credits.toFixed(2)} / {cap} credits</Badge>} />
          <ol className="divide-y divide-border" data-testid="stepper">
            {STEP_ORDER.map((s) => {
              const st = steps[s];
              return (
                <li key={s} className="flex items-start gap-3 px-5 py-3" data-status={st.status}>
                  <span className="mt-0.5">{ICON[st.status]}</span>
                  <div className="min-w-0"><div className={st.status === "pending" ? "text-sm text-muted" : "text-sm font-medium"}>{STEP_LABEL[s]}</div>
                    {st.note && <div className="mt-0.5 text-xs text-warn">{st.note}</div>}</div>
                </li>
              );
            })}
          </ol>
          <div className="px-5 pb-4"><Meter value={credits} max={cap} tone={credits / cap > 0.8 ? "warn" : "brand"} label="credits used vs per-mission cap" /></div>
        </Card>

        <div className="space-y-4 lg:col-span-3">
          <Card>
            <CardHeader title="Activity" sub="What the engine is doing, in plain terms" />
            <div ref={logRef} className="max-h-64 space-y-1 overflow-y-auto px-5 py-3 font-mono text-xs" data-testid="activity-log" aria-live="polite">
              {log.length === 0 && <div className="text-muted">Waiting for the first step…</div>}
              {log.filter((e) => e.msg !== "started" && e.msg !== "done").map((e, i) => (
                <div key={i} className={e.msg === "warning" || e.msg === "failed" ? "text-warn" : ""}>
                  <span className="text-muted">{STEP_LABEL[e.step ?? ""] ?? e.step}</span> · {e.msg}{e.warning ? `: ${e.warning}` : ""}
                </div>))}
            </div>
          </Card>
          <Card>
            <CardHeader title="Crustdata calls" sub="Every call is logged with its cost" right={<Badge tone="brand">{calls.length} calls</Badge>} />
            <div className="max-h-64 overflow-auto" data-testid="calls-table">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-surface text-muted"><tr><th className="px-5 py-2">Tool</th><th>Status</th><th>Results</th><th>Indexed total</th><th className="pr-5 text-right">Credits</th></tr></thead>
                <tbody>{calls.map((c, i) => {
                  const bad = /error|simulated/.test(c.msg ?? "");
                  return (
                    <tr key={i} className="border-t border-border">
                      <td className="px-5 py-1.5 font-mono">{(c.msg ?? "").split(" ")[0]}</td>
                      <td><Badge tone={bad ? "bad" : (c.msg ?? "").includes("cached") || (c.msg ?? "").includes("replayed") ? "neutral" : "good"}>{(c.msg ?? "").split(" ").slice(1).join(" ")}{c.error ? ` · ${c.error}` : ""}</Badge></td>
                      <td>{c.n ?? "–"}</td><td>{c.total ?? "–"}</td><td className="pr-5 text-right tabular-nums">{c.credit != null ? c.credit.toFixed(2) : "–"}</td>
                    </tr>);
                })}</tbody>
              </table>
              {calls.length === 0 && <div className="px-5 py-4 text-xs text-muted">No calls yet.</div>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
