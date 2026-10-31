"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, Copy, Mail, Users } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button, Card, CardHeader, Field, Notice, PageHeader, Pill, Segmented, SidePanel, Skeleton, inputCls, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { priority, score } from "@/lib/format";
import type { Crm, CrmCompany, CrmTask } from "@/lib/types";

function DraftEditor({ id, t }: { id: string; t: CrmTask }) {
  const qc = useQueryClient(); const toast = useToast();
  const [text, setText] = useState(t.draft_text ?? "");
  const [copied, setCopied] = useState(false);
  const save = useMutation({ mutationFn: () => api.patchTask(id, t.id, { draft_text: text }), onSuccess: () => { toast("Draft saved", "ok"); qc.invalidateQueries({ queryKey: ["crm", id] }); } });
  return (
    <div className="rounded-md border border-line" data-testid="draft-card">
      <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2"><span className="text-[13px] font-medium">{t.title.replace(/^Draft outreach to /, "To ")}</span><Pill tone="warn" dot={false}>Not sent</Pill></div>
      <textarea aria-label={`Draft: ${t.title}`} value={text} onChange={(e) => setText(e.target.value)} rows={8} className="block w-full resize-y border-0 bg-surface px-3 py-2.5 text-[13px] leading-relaxed text-ink focus:outline-none" />
      <div className="flex items-center gap-2 border-t border-line px-3 py-2">
        <Button size="sm" disabled={text === (t.draft_text ?? "") || save.isPending} onClick={() => save.mutate()}>Save edits</Button>
        <Button size="sm" variant="secondary" onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); toast("Copied to clipboard"); setTimeout(() => setCopied(false), 1500); }}>{copied ? <Check size={14} /> : <Copy size={14} />}Copy</Button>
        <span className="ml-auto text-xs text-muted">Send it yourself from your email</span>
      </div>
    </div>
  );
}

export default function PipelinePage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient(); const toast = useToast();
  const q = useQuery({ queryKey: ["crm", id], queryFn: () => api.crm(id) });
  const mission = useQuery({ queryKey: ["mission", id], queryFn: () => api.mission(id) });
  const [seg, setSeg] = useState<"all" | "Wave 1" | "Wave 2" | "Research Needed">("all");
  const [dragId, setDragId] = useState<number | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const move = useMutation({
    mutationFn: ({ rowId, stage }: { rowId: number; stage: string }) => api.setStage(id, rowId, stage),
    onMutate: async ({ rowId, stage }) => {
      await qc.cancelQueries({ queryKey: ["crm", id] });
      const prev = qc.getQueryData<Crm>(["crm", id]);
      if (prev) qc.setQueryData<Crm>(["crm", id], { ...prev, companies: prev.companies.map((c) => (c.id === rowId ? { ...c, stage } : c)) });
      return { prev };
    },
    onSuccess: (_d, v) => toast(`Moved to ${v.stage}`, "ok"),
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(["crm", id], ctx.prev); toast("Couldn't update the stage", "bad"); },
    onSettled: () => qc.invalidateQueries({ queryKey: ["crm", id] }),
  });
  const toggleTask = useMutation({ mutationFn: ({ t, done }: { t: CrmTask; done: boolean }) => api.patchTask(id, t.id, { status: done ? "done" : "todo" }), onSettled: () => qc.invalidateQueries({ queryKey: ["crm", id] }) });

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-96" /></div>;
  if (q.error || !q.data) return <Notice tone="bad" title="Couldn't load the pipeline">{(q.error as Error | null)?.message}</Notice>;
  const crm = q.data; const b = mission.data?.brief;
  const market = b ? `${b.target_industry} in ${b.target_country}` : "Research";
  const shown = crm.companies.filter((c) => seg === "all" || c.segment === seg);
  const tasksFor = (cid: number) => crm.tasks.filter((t) => t.company_id === cid);
  const checklist = crm.tasks.filter((t) => t.company_id == null);
  const open = crm.companies.find((c) => c.id === openId) ?? null;
  const openTasks = open ? tasksFor(open.id) : [];

  return (
    <>
      <PageHeader crumbs={[{ href: "/research", label: "Research" }, { href: `/research/${id}`, label: market }, { label: "Pipeline" }]} title="Pipeline"
        description="Track each company from first look to won. Drag cards between stages or open one to read and edit its draft message. Nothing is ever sent for you." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Priority filter" value={seg} onChange={setSeg} options={[{ id: "all", label: `All (${crm.companies.length})` }, { id: "Wave 1", label: "Contact first" }, { id: "Wave 2", label: "Next in line" }, { id: "Research Needed", label: "Needs research" }]} />
        <div className="flex gap-4 text-[13px] text-muted"><span className="flex items-center gap-1.5"><Users size={14} />{crm.counts.people} decision-makers</span><span className="flex items-center gap-1.5"><Mail size={14} />{crm.counts.unsent_drafts} drafts ready</span></div>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-3" data-testid="board">
        {crm.stages.map((stage) => {
          const col = shown.filter((c) => c.stage === stage);
          return (
            <div key={stage} data-testid={`col-${stage}`} onDragOver={(e) => e.preventDefault()}
              onDrop={() => { if (dragId != null && crm.companies.find((c) => c.id === dragId)?.stage !== stage) move.mutate({ rowId: dragId, stage }); setDragId(null); }}
              className={clsx("flex w-64 shrink-0 flex-col rounded-lg border border-line bg-subtle/60", dragId != null && "border-dashed border-line-strong")}>
              <div className="flex items-center justify-between px-3 py-2.5 text-[13px] font-medium text-ink-2">{stage}<span className="tabular text-muted">{col.length}</span></div>
              <div className="max-h-[30rem] flex-1 space-y-2 overflow-y-auto px-2 pb-2">
                {col.length === 0 && <div className="rounded-md border border-dashed border-line px-3 py-6 text-center text-xs text-muted">Drop companies here</div>}
                {col.map((c: CrmCompany) => {
                  const p = priority(c.segment); const ts = tasksFor(c.id); const drafts = ts.filter((t) => t.task_type === "outreach_draft").length;
                  return (
                    <div key={c.id} role="button" tabIndex={0} draggable onDragStart={() => setDragId(c.id)} onDragEnd={() => setDragId(null)}
                      onClick={() => setOpenId(c.id)} onKeyDown={(e) => e.key === "Enter" && setOpenId(c.id)} data-testid="company-card"
                      className="cursor-pointer rounded-md border border-line bg-surface p-3 shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:border-line-strong">
                      <div className="flex items-start justify-between gap-2"><div className="min-w-0 text-sm font-medium leading-snug text-ink">{c.name}</div><span className="tabular text-xs font-semibold text-ink-2">{score(c.fit_score)}</span></div>
                      <div className="mt-0.5 truncate text-xs text-muted">{c.domain ?? "No website"}</div>
                      <div className="mt-2.5 flex items-center justify-between gap-2"><Pill tone={p.tone}>{p.label}</Pill>{drafts > 0 && <span className="flex items-center gap-1 text-xs text-muted"><Mail size={12} />{drafts}</span>}</div>
                    </div>);
                })}
              </div>
            </div>);
        })}
      </div>

      {checklist.length > 0 && (
        <Card className="mt-6 max-w-2xl">
          <CardHeader title="Before you reach out" description="A short checklist for this market." />
          <ul className="divide-y divide-line" data-testid="tasks">{checklist.map((t) => (
            <li key={t.id}><label className="flex cursor-pointer items-center gap-3 px-5 py-3 text-sm">
              <input type="checkbox" className="h-4 w-4" checked={t.status === "done"} onChange={(e) => toggleTask.mutate({ t, done: e.target.checked })} />
              <span className={t.status === "done" ? "text-muted line-through" : "text-ink"}>{t.title}</span></label></li>))}</ul>
        </Card>)}

      <SidePanel open={!!open} onClose={() => setOpenId(null)} title={open?.name ?? ""} subtitle={open?.domain ?? undefined}>
        {open && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Stage" htmlFor="stage"><select id="stage" data-testid="stage-select" className={inputCls} value={open.stage} onChange={(e) => move.mutate({ rowId: open.id, stage: e.target.value })}>{crm.stages.map((s) => <option key={s}>{s}</option>)}</select></Field>
              <div><div className="mb-1.5 text-[13px] font-medium text-ink-2">Priority</div><Pill tone={priority(open.segment).tone}>{priority(open.segment).label}</Pill><div className="mt-1 text-xs text-muted">Match score {score(open.fit_score)}</div></div>
            </div>
            <section>
              <h3 className="mb-2 text-sm font-semibold">Decision-makers</h3>
              {crm.people.filter((p) => p.company_id === open.id).length === 0 ? <p className="text-[13px] text-muted">None found yet.</p> : (
                <ul className="space-y-1.5">{crm.people.filter((p) => p.company_id === open.id).map((p) => (
                  <li key={p.id} className="flex items-center justify-between rounded-md border border-line px-3 py-2 text-sm"><span className="font-medium">{p.name}</span><span className="text-[13px] text-muted">{p.title}</span></li>))}</ul>)}
            </section>
            {openTasks.filter((t) => t.task_type === "outreach_draft").length > 0 && (
              <section className="space-y-3"><h3 className="text-sm font-semibold">Draft messages</h3>
                {openTasks.filter((t) => t.task_type === "outreach_draft").map((t) => <DraftEditor key={`${t.id}-${t.draft_text?.length}`} id={id} t={t} />)}</section>)}
            {openTasks.filter((t) => t.task_type !== "outreach_draft").length > 0 && (
              <section><h3 className="mb-2 text-sm font-semibold">To do</h3>
                <ul className="space-y-1">{openTasks.filter((t) => t.task_type !== "outreach_draft").map((t) => (
                  <li key={t.id}><label className="flex cursor-pointer items-start gap-3 rounded-md px-1 py-1.5 text-sm hover:bg-subtle">
                    <input type="checkbox" className="mt-0.5 h-4 w-4" checked={t.status === "done"} onChange={(e) => toggleTask.mutate({ t, done: e.target.checked })} />
                    <span className={t.status === "done" ? "text-muted line-through" : ""}>{t.title}</span></label></li>))}</ul></section>)}
          </div>)}
      </SidePanel>
    </>
  );
}
