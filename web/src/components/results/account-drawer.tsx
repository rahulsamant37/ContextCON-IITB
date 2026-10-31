"use client";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { Badge, Drawer, Meter, Skeleton, statusTone, waveTone } from "@/components/ui";
import { api } from "@/lib/api";
import { COMPONENT_LABEL, money, num, pct, UNKNOWN } from "@/lib/format";
import { SourceViewer } from "./source-viewer";

export function AccountDrawer({ missionId, companyId, onClose }: { missionId: string; companyId: string | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["account", missionId, companyId], queryFn: () => api.account(missionId, companyId!), enabled: !!companyId });
  const [open, setOpen] = useState<string | null>(null);
  const a = q.data?.account;
  return (
    <Drawer open={!!companyId} onClose={onClose} title={a ? <span className="flex flex-wrap items-center gap-2">{a.name}{a.wave && <Badge tone={waveTone(a.wave)}>{a.wave}</Badge>}</span> : "Account"}>
      {q.isLoading && <Skeleton className="h-64" />}
      {q.data && a && (
        <div className="space-y-6" data-testid="account-detail">
          <div className="text-sm">
            {a.domain && <a className="inline-flex items-center gap-1 text-brand underline" href={`https://${a.domain}`} target="_blank" rel="noreferrer noopener">{a.domain}<ExternalLink size={12} /></a>}
            <span className="ml-3 text-xs text-muted">Crustdata ID {a.company_id} · identity matched by {a.identity.method}</span>
            {a.description && <p className="mt-2 text-muted">{a.description.slice(0, 420)}{a.description.length > 420 ? "…" : ""}</p>}
            <p className="mt-1 text-xs text-muted">Description is the provider&apos;s text, not our claim.</p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[["Headcount", num(a.employee_count)], ["6-month growth", pct(a.headcount_growth_6m)], ["Open roles", a.open_roles == null ? UNKNOWN : String(a.open_roles)], ["Funding", money(a.funding_total, "USD")]].map(([k, v]) => (
              <div key={k} className="rounded-lg bg-surface-2 p-3"><div className="text-xs text-muted">{k}</div><div className={`mt-0.5 text-sm font-semibold ${v === UNKNOWN ? "text-warn" : ""}`}>{v}</div></div>
            ))}
          </div>

          <section>
            <h4 className="mb-2 text-sm font-semibold">Why this score</h4>
            <p className="mb-3 text-xs text-muted">Fit {a.fit_score ?? UNKNOWN} is earned points over the points that could be assessed. Data coverage ({Math.round(a.data_coverage * 100)}%, {a.confidence} confidence) is shown separately. Hatched bars are unknown: no evidence, and no penalty.</p>
            <div className="space-y-2">
              {q.data.breakdown.map((b) => {
                const unknown = typeof b.points !== "number";
                return (
                  <div key={b.component} className="grid grid-cols-[10rem_1fr_4.5rem] items-center gap-3 text-sm">
                    <span>{COMPONENT_LABEL[b.component] ?? b.component}</span>
                    <Meter value={unknown ? null : (b.points as number)} max={b.max} tone={unknown ? "neutral" : "brand"} />
                    <span className="text-right text-xs tabular-nums text-muted">{unknown ? "unknown" : `${b.points}/${b.max}`}</span>
                  </div>);
              })}
            </div>
            {a.icp_reasons.length > 0 && <ul className="mt-3 list-disc pl-5 text-xs text-muted">{a.icp_reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
          </section>

          <section>
            <h4 className="mb-2 text-sm font-semibold">Buyers</h4>
            {q.data.people.length === 0 ? <p className="text-sm text-muted">{a.buyer_status === "buyer_not_found" ? "No verified contact in the target roles was found. Nothing is guessed." : "Buyers were not searched for this account."}</p> : (
              <ul className="space-y-2">{q.data.people.map((p) => (
                <li key={p.person_id ?? p.name} className="rounded-lg border border-border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2 font-medium">{p.name}<Badge tone="good">employer verified · {p.verification_method}</Badge>{p.role_matched && <Badge tone="brand">{p.role_matched}</Badge>}</div>
                  <div className="text-xs text-muted">{p.current_title ?? UNKNOWN}</div>
                  {p.missing_flags.length > 0 && <div className="mt-1 text-xs text-warn">{p.missing_flags.join(", ")}</div>}
                </li>))}</ul>)}
          </section>

          <section>
            <h4 className="mb-2 text-sm font-semibold">Evidence ({q.data.evidence.length})</h4>
            <ul className="divide-y divide-border rounded-lg border border-border">
              {q.data.evidence.map((e) => (
                <li key={e.evidence_id}>
                  <button className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => setOpen(open === e.evidence_id ? null : e.evidence_id)} aria-expanded={open === e.evidence_id}>
                    <span className="min-w-0 truncate">{e.claim}</span><Badge tone={statusTone(e.status)}>{e.status}</Badge>
                  </button>
                  {open === e.evidence_id && <div className="border-t border-border bg-surface px-3 py-3"><SourceViewer missionId={missionId} evidenceId={e.evidence_id} /></div>}
                </li>))}
            </ul>
          </section>
        </div>)}
    </Drawer>
  );
}
