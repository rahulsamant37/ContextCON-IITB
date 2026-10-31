"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Copy, Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Callout, Card, CardHeader, Empty, Skeleton, statusTone, waveTone } from "@/components/ui";
import { api } from "@/lib/api";
import type { Crm, CrmCompany, CrmTask } from "@/lib/types";

function DraftEditor({ id, t, who }: { id: string; t: CrmTask; who: string }) {
  const qc = useQueryClient();
  const [text, setText] = useState(t.draft_text ?? "");
  const [copied, setCopied] = useState(false);
  const save = useMutation({ mutationFn: (body: { status?: string; draft_text?: string }) => api.patchTask(id, t.id, body), onSuccess: () => qc.invalidateQueries({ queryKey: ["crm", id] }) });
  const dirty = text !== (t.draft_text ?? "");
  return (
    <Card className="p-4" data-testid="draft-card">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><div className="text-sm font-medium">{t.title}</div><Badge tone="warn">UNSENT draft · {who}</Badge></div>
      <textarea aria-label={`Draft for ${t.title}`} value={text} onChange={(e) => setText(e.target.value)} rows={7} className="w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs leading-relaxed focus:border-brand" />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate({ draft_text: text })}><Save size={14} />Save edits</Button>
        <Button size="sm" variant="secondary" onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "Copied" : "Copy"}</Button>
        <select aria-label="Task status" value={t.status} onChange={(e) => save.mutate({ status: e.target.value })} className="ml-auto rounded-lg border border-border bg-surface px-2 py-1 text-xs">
          {["draft_unsent", "in_progress", "done", "skipped"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select>
      </div>
      <p className="mt-2 text-xs text-muted">Stored locally. There is no send button: a person reviews, personalises and sends from their own tools.</p>
    </Card>
  );
}

export default function CrmPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["crm", id], queryFn: () => api.crm(id) });
  const [seg, setSeg] = useState("all");
  const [dragId, setDragId] = useState<number | null>(null);
  const [allTasks, setAllTasks] = useState(false);
  const move = useMutation({
    mutationFn: ({ rowId, stage }: { rowId: number; stage: string }) => api.setStage(id, rowId, stage),
    onMutate: async ({ rowId, stage }) => {
      await qc.cancelQueries({ queryKey: ["crm", id] });
      const prev = qc.getQueryData<Crm>(["crm", id]);
      if (prev) qc.setQueryData<Crm>(["crm", id], { ...prev, companies: prev.companies.map((c) => (c.id === rowId ? { ...c, stage } : c)) });
      return { prev };
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(["crm", id], ctx.prev),
    onSettled: () => qc.invalidateQueries({ queryKey: ["crm", id] }),
  });

  if (q.isLoading) return <div className="space-y-3"><Skeleton className="h-10 w-1/3" /><Skeleton className="h-72" /></div>;
  if (q.error || !q.data) return <Callout tone="bad" title="Could not load the CRM">{(q.error as Error | null)?.message}</Callout>;
  const crm = q.data;
  const byRow = new Map(crm.companies.map((c) => [c.id, c]));
  const shown = crm.companies.filter((c) => seg === "all" || c.segment === seg);
  const drafts = crm.tasks.filter((t) => t.task_type === "outreach_draft");
  const others = crm.tasks.filter((t) => t.task_type !== "outreach_draft");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><Link href={`/missions/${id}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft size={14} />Back to results</Link>
          <h1 className="mt-1 text-2xl font-semibold">CRM board</h1>
          <p className="text-sm text-muted">{crm.counts.companies} accounts · {crm.counts.people} contacts · {crm.counts.unsent_drafts} unsent drafts. Changes are saved to the local database.</p></div>
        <div className="flex gap-1.5" role="group" aria-label="Segment filter">{["all", "Wave 1", "Wave 2", "Research Needed"].map((s) => (
          <button key={s} onClick={() => setSeg(s)} className={`rounded-full border px-3 py-1 text-xs font-medium ${seg === s ? "border-brand bg-brand-soft text-brand" : "border-border hover:bg-surface-2"}`}>{s === "all" ? "All segments" : s}</button>))}</div>
      </div>

      <div className="grid gap-3 overflow-x-auto pb-2" style={{ gridTemplateColumns: `repeat(${crm.stages.length}, minmax(13rem, 1fr))` }} data-testid="board">
        {crm.stages.map((stage) => {
          const col = shown.filter((c) => c.stage === stage);
          return (
            <div key={stage} data-testid={`col-${stage}`} onDragOver={(e) => e.preventDefault()} onDrop={() => { if (dragId != null && byRow.get(dragId)?.stage !== stage) move.mutate({ rowId: dragId, stage }); setDragId(null); }}
              className="min-h-40 rounded-xl border border-border bg-surface-2 p-2">
              <div className="mb-2 flex items-center justify-between px-1 text-xs font-semibold uppercase tracking-wide text-muted">{stage}<span className="rounded-full bg-surface px-1.5 py-0.5">{col.length}</span></div>
              <div className="max-h-[32rem] space-y-2 overflow-y-auto pr-0.5">{col.map((c: CrmCompany) => (
                <div key={c.id} draggable onDragStart={() => setDragId(c.id)} onDragEnd={() => setDragId(null)} data-testid="company-card"
                  className="cursor-grab rounded-lg border border-border bg-surface p-3 shadow-sm active:cursor-grabbing">
                  <div className="text-sm font-medium">{c.name}</div><div className="text-xs text-muted">{c.domain ?? "unknown"}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5"><Badge tone={waveTone(c.segment)}>{c.segment ?? "n/a"}</Badge><Badge tone={statusTone(c.verification_status)}>{c.verification_status}</Badge>{c.fit_score != null && <span className="text-xs tabular-nums text-muted">fit {c.fit_score}</span>}</div>
                  <select aria-label={`Stage for ${c.name}`} value={c.stage} onChange={(e) => move.mutate({ rowId: c.id, stage: e.target.value })} className="mt-2 w-full rounded-md border border-border bg-surface px-1.5 py-1 text-xs">{crm.stages.map((s) => <option key={s}>{s}</option>)}</select>
                </div>))}</div>
            </div>);
        })}
      </div>

      <section>
        <h2 className="mb-2 text-lg font-semibold">Outreach drafts <span className="text-sm font-normal text-muted">({drafts.length}, none sent)</span></h2>
        {drafts.length === 0 ? <Empty title="No drafts yet">Drafts are created for accounts that have a verified buyer.</Empty> : (
          <div className="grid gap-4 lg:grid-cols-2">{drafts.map((t) => <DraftEditor key={t.id} id={id} t={t} who={byRow.get(t.company_id ?? -1)?.name ?? "account"} />)}</div>)}
      </section>

      <section>
        <Card><CardHeader title={`Tasks and checklist (${others.length})`} sub="Research gaps, qualification and launch-checklist items" />
          <ul className="divide-y divide-border" data-testid="tasks">{(allTasks ? others : others.slice(0, 8)).map((t) => (
            <li key={t.id} className="flex items-center gap-3 px-5 py-2.5 text-sm">
              <input type="checkbox" aria-label={`Mark done: ${t.title}`} checked={t.status === "done"} onChange={(e) => api.patchTask(id, t.id, { status: e.target.checked ? "done" : "todo" }).then(() => qc.invalidateQueries({ queryKey: ["crm", id] }))} />
              <span className={t.status === "done" ? "text-muted line-through" : ""}>{t.title}</span>
              <Badge className="ml-auto" tone="neutral">{t.task_type.replace("_", " ")}</Badge></li>))}</ul>
          {others.length > 8 && <button onClick={() => setAllTasks(!allTasks)} className="w-full border-t border-border px-5 py-2.5 text-sm font-medium text-brand hover:bg-surface-2">{allTasks ? "Show fewer" : `Show all ${others.length} tasks`}</button>}</Card>
      </section>
    </div>
  );
}
