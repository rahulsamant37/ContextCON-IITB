"use client";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronRight, ExternalLink, HelpCircle, X } from "lucide-react";
import { useState } from "react";
import { LinkButton, Pill, SidePanel, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { COMPONENT_LABEL, money, num, pct, priority, score, SOURCE_STATUS, UNKNOWN } from "@/lib/format";
import { SourceViewer } from "./source-viewer";

export function CompanyPanel({ missionId, companyId, onClose }: { missionId: string; companyId: string | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["account", missionId, companyId], queryFn: () => api.account(missionId, companyId!), enabled: !!companyId });
  const [open, setOpen] = useState<string | null>(null);
  const a = q.data?.account;
  // search and enrichment can both report the same fact; show each distinct fact once
  const facts = (q.data?.evidence ?? []).filter((e, i, all) => all.findIndex((x) => x.claim === e.claim) === i);
  const p = a ? priority(a.wave) : null;
  return (
    <SidePanel open={!!companyId} onClose={onClose} title={a?.name ?? "Company"}
      subtitle={a && <span className="flex items-center gap-2">{a.domain && <a className="inline-flex items-center gap-1 hover:text-ink" href={`https://${a.domain}`} target="_blank" rel="noreferrer noopener">{a.domain}<ExternalLink size={11} /></a>}{p && <Pill tone={p.tone}>{p.label}</Pill>}</span>}
      footer={<div className="flex justify-end"><LinkButton href={`/research/${missionId}/pipeline`} variant="secondary" size="sm">Open in pipeline</LinkButton></div>}>
      {q.isLoading && <Skeleton className="h-72" />}
      {q.data && a && (
        <div className="space-y-7" data-testid="account-detail">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line">
            {[["Employees", num(a.employee_count)], ["Team growth (6 months)", pct(a.headcount_growth_6m)], ["Open jobs", a.open_roles == null ? UNKNOWN : String(a.open_roles)], ["Total funding", money(a.funding_total, "USD", true)]].map(([k, v]) => (
              <div key={k} className="bg-surface px-4 py-3"><div className="text-xs text-muted">{k}</div><div className={`tabular mt-0.5 font-semibold ${v === UNKNOWN ? "text-muted" : "text-ink"}`}>{v}</div></div>))}
          </div>

          <section>
            <div className="flex items-baseline justify-between"><h3 className="text-sm font-semibold">Why it&apos;s a match</h3><span className="tabular text-sm"><b>{score(a.fit_score)}</b><span className="text-muted"> / 100</span></span></div>
            <p className="mt-1 text-[13px] text-muted">Scored only on information we could find. Missing information isn&apos;t counted against the company; it lowers data completeness ({Math.round(a.data_coverage * 100)}%) instead.</p>
            <ul className="mt-3 divide-y divide-line rounded-md border border-line">
              {q.data.breakdown.map((b) => {
                const unknown = typeof b.points !== "number"; const pts = unknown ? 0 : (b.points as number);
                return (
                  <li key={b.component} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                    {unknown ? <HelpCircle size={16} className="text-muted" /> : pts >= b.max * 0.99 ? <Check size={16} className="text-ok" /> : pts > 0 ? <Check size={16} className="text-warn" /> : <X size={16} className="text-bad" />}
                    <span className="flex-1">{COMPONENT_LABEL[b.component] ?? b.component}</span>
                    <span className="tabular text-[13px] text-muted">{unknown ? "No data" : `${Math.round(pts * 10) / 10} / ${b.max}`}</span>
                  </li>);
              })}
            </ul>
          </section>

          <section>
            <h3 className="text-sm font-semibold">Decision-makers</h3>
            {q.data.people.length === 0 ? <p className="mt-1 text-[13px] text-muted">{a.buyer_status === "buyer_not_found" ? "We searched and found no one in your buyer roles. We don't guess." : "Not searched yet; we search the highest-ranked companies first."}</p> : (
              <ul className="mt-2 space-y-2">{q.data.people.map((x) => (
                <li key={x.person_id ?? x.name} className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2.5">
                  <div><div className="text-sm font-medium">{x.name}</div><div className="text-[13px] text-muted">{x.current_title ?? UNKNOWN}</div></div>
                  <Pill tone="ok" title="Their current employer matches this company's record">Employer confirmed</Pill></li>))}</ul>)}
          </section>

          {a.description && (
            <section><h3 className="text-sm font-semibold">About</h3><p className="mt-1 text-[13px] leading-relaxed text-ink-2">{a.description.slice(0, 500)}{a.description.length > 500 ? "…" : ""}</p>
              <p className="mt-1 text-xs text-muted">Company&apos;s own description, via Crustdata.</p></section>)}

          <section>
            <h3 className="text-sm font-semibold">Sources <span className="font-normal text-muted">({facts.length} facts)</span></h3>
            <ul className="mt-2 divide-y divide-line rounded-md border border-line">
              {facts.map((e) => (
                <li key={e.evidence_id}>
                  <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] hover:bg-subtle" onClick={() => setOpen(open === e.evidence_id ? null : e.evidence_id)} aria-expanded={open === e.evidence_id}>
                    <ChevronRight size={14} className={`shrink-0 text-muted transition ${open === e.evidence_id ? "rotate-90" : ""}`} />
                    <span className="min-w-0 flex-1 truncate">{e.claim}</span><Pill tone={SOURCE_STATUS[e.status]?.tone}>{SOURCE_STATUS[e.status]?.label}</Pill>
                  </button>
                  {open === e.evidence_id && <div className="border-t border-line px-3 py-3"><SourceViewer missionId={missionId} evidenceId={e.evidence_id} /></div>}
                </li>))}
            </ul>
          </section>
        </div>)}
    </SidePanel>
  );
}
