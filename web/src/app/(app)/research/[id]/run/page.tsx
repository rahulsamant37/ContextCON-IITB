"use client";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ArrowRight, Check, ChevronDown, Loader2, Minus, X } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Card, LinkButton, Notice, PageHeader, td, th } from "@/components/ui";
import { api } from "@/lib/api";
import { STEP_DETAIL, STEP_LABEL, STEP_ORDER } from "@/lib/format";
import { useMissionEvents } from "@/lib/use-events";

function StepIcon({ status }: { status: string }) {
  if (status === "done") return <span className="grid h-6 w-6 place-items-center rounded-full bg-ok text-white dark:text-[#0b0d10]"><Check size={14} strokeWidth={3} /></span>;
  if (status === "running") return <span className="grid h-6 w-6 place-items-center rounded-full border-2 border-accent"><Loader2 size={13} className="animate-spin text-accent" /></span>;
  if (status === "warning") return <span className="grid h-6 w-6 place-items-center rounded-full bg-warn-soft text-warn"><AlertTriangle size={13} /></span>;
  if (status === "failed") return <span className="grid h-6 w-6 place-items-center rounded-full bg-bad-soft text-bad"><X size={14} /></span>;
  if (status === "skipped") return <span className="grid h-6 w-6 place-items-center rounded-full bg-subtle text-muted"><Minus size={14} /></span>;
  return <span className="h-6 w-6 rounded-full border-2 border-line-strong" />;
}

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const status = useQuery({ queryKey: ["status", id], queryFn: () => api.status(id), retry: false });
  const { ended, connection, steps, credits, calls, log, finalState, error } = useMissionEvents(id);
  const [elapsed, setElapsed] = useState(0);
  const [showLog, setShowLog] = useState(false);
  const t0 = useRef<number | null>(null);

  useEffect(() => {
    if (ended) return;
    const t = setInterval(() => { t0.current ??= Date.now(); setElapsed(Math.round((Date.now() - t0.current) / 1000)); }, 1000);
    return () => clearInterval(t);
  }, [ended]);
  useEffect(() => { if (ended && !error) { const t = setTimeout(() => router.replace(`/research/${id}`), 1500); return () => clearTimeout(t); } }, [ended, error, id, router]);

  if (status.error) return (
    <Notice tone="bad" title="We couldn't find this research" action={<LinkButton href="/research/new" size="sm">New research</LinkButton>}>
      It may have been interrupted by a server restart. Start it again; nothing is lost from earlier research.
    </Notice>);

  const done = STEP_ORDER.filter((s) => ["done", "warning", "skipped", "failed"].includes(steps[s].status)).length;
  const current = STEP_ORDER.find((s) => steps[s].status === "running");
  const pct = ended ? 100 : Math.max(4, Math.round((done / STEP_ORDER.length) * 100));
  const found = calls.find((c) => (c.msg ?? "").startsWith("company_search") && c.total != null)?.total;
  const retried = calls.some((c) => (c.msg ?? "").includes("simulated_failure") || (c.msg ?? "").includes("error"));
  const failed = ended && (error || finalState === "failed");

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader crumbs={[{ href: "/research", label: "Research" }, { label: ended ? "Finished" : "In progress" }]}
        title={failed ? "The research couldn't be completed" : ended ? "Your research is ready" : "Researching your market"}
        description={status.data?.prompt ?? undefined} />

      <Card className="overflow-hidden">
        <div className="px-6 pb-5 pt-6">
          <div className="flex items-baseline justify-between gap-3">
            <div className="text-[15px] font-medium text-ink" aria-live="polite">{ended ? (failed ? "Stopped" : "Done") : current ? STEP_LABEL[current] : "Starting…"}</div>
            <div className="tabular text-[13px] text-muted">{ended ? "" : `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`}</div>
          </div>
          <p className="mt-0.5 text-[13px] text-muted">{ended ? (failed ? "Nothing was made up to fill the gaps. See the reasons below." : "Opening your results…") : current ? STEP_DETAIL[current] : "Usually takes about a minute."}</p>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-subtle"><div className={clsx("h-full rounded-full transition-all duration-700", failed ? "bg-bad" : "bg-accent")} style={{ width: `${pct}%` }} /></div>
        </div>
        {(found != null || credits > 0) && (
          <div className="grid grid-cols-2 border-t border-line text-sm">
            <div className="px-6 py-3"><div className="text-xs text-muted">Matching companies</div><div className="tabular font-semibold">{found != null ? found.toLocaleString() : "…"}</div></div>
            <div className="border-l border-line px-6 py-3"><div className="text-xs text-muted">Data cost so far</div><div className="tabular font-semibold">{credits.toFixed(1)} credits</div></div>
          </div>)}
        <ol className="border-t border-line px-6 py-4" data-testid="stepper">
          {STEP_ORDER.map((s, i) => (
            <li key={s} className="relative flex gap-3 pb-4 last:pb-0" data-status={steps[s].status}>
              {i < STEP_ORDER.length - 1 && <span className="absolute left-3 top-7 h-[calc(100%-1.5rem)] w-px bg-line" aria-hidden />}
              <StepIcon status={steps[s].status} />
              <div className="min-w-0 pt-0.5">
                <div className={clsx("text-sm", steps[s].status === "pending" ? "text-muted" : "font-medium text-ink")}>{STEP_LABEL[s]}</div>
                {steps[s].note && <div className="mt-0.5 text-[13px] text-warn">{steps[s].note}</div>}
              </div>
            </li>))}
        </ol>
      </Card>

      {retried && !ended && <div className="mt-4"><Notice tone="info" title="A request failed and was retried automatically">Your research continues; temporary errors are handled for you.</Notice></div>}
      {connection === "lost" && !ended && <div className="mt-4"><Notice tone="warn" title="Connection interrupted">The research keeps running on the server. Refresh this page to reconnect.</Notice></div>}
      {error && <div className="mt-4"><Notice tone="bad" title="Something went wrong on the server">{error}</Notice></div>}
      {ended && <div className="mt-4 flex justify-end"><LinkButton href={`/research/${id}`} data-testid="open-results">{failed ? "See what happened" : "View results"}<ArrowRight size={15} /></LinkButton></div>}

      <div className="mt-6">
        <button onClick={() => setShowLog(!showLog)} className="flex items-center gap-1.5 text-[13px] font-medium text-muted hover:text-ink" aria-expanded={showLog}>
          <ChevronDown size={15} className={clsx("transition", showLog && "rotate-180")} />Technical details ({calls.length} data requests)</button>
        {showLog && (
          <Card className="mt-3 overflow-hidden">
            <div className="max-h-72 overflow-auto" data-testid="calls-table">
              <table className="w-full text-[13px]"><thead className="sticky top-0 border-b border-line bg-surface"><tr><th className={th}>Request</th><th className={th}>Result</th><th className={`${th} text-right`}>Rows</th><th className={`${th} text-right`}>Credits</th></tr></thead>
                <tbody>{calls.map((c, i) => {
                  const [tool, ...rest] = (c.msg ?? "").split(" ");
                  return <tr key={i} className="border-b border-line last:border-0"><td className={`${td} font-mono text-xs`}>{tool}</td><td className={td}>{rest.join(" ").replace("_", " ")}{c.error ? ` · ${c.error}` : ""}</td><td className={`${td} tabular text-right`}>{c.n ?? "–"}</td><td className={`${td} tabular text-right`}>{c.credit != null ? c.credit.toFixed(2) : "–"}</td></tr>;
                })}</tbody></table>
            </div>
            <div className="max-h-48 space-y-0.5 overflow-auto border-t border-line px-4 py-3 font-mono text-xs text-muted" data-testid="activity-log">
              {log.filter((e) => !["started", "done"].includes(e.msg ?? "")).map((e, i) => <div key={i}>{STEP_LABEL[e.step ?? ""] ?? e.step}: {e.msg}{e.warning ? ` (${e.warning})` : ""}</div>)}
            </div>
          </Card>)}
      </div>
    </div>
  );
}
