"use client";
import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, FileSpreadsheet, FileText, FileJson, Kanban } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge, Callout, Card, Drawer, Empty, Skeleton, statusTone, type Tone } from "@/components/ui";
import { api } from "@/lib/api";
import { num, UNKNOWN } from "@/lib/format";
import type { Account, Competitor, Mission, Source } from "@/lib/types";
import { SourceViewer } from "./source-viewer";

export function Buyers({ m }: { m: Mission }) {
  const searched = m.accounts.filter((a) => a.buyer_status !== "not_searched");
  const notSearched = m.accounts.length - searched.length;
  if (searched.length === 0) return <Empty title="Buyers were not searched">Buyer mapping did not run or failed; see the warnings on the Overview tab.</Empty>;
  return (
    <div className="space-y-3">
      <Callout tone="neutral" title="How buyers are verified">A person is listed only if their current employer matches the account&apos;s Crustdata company ID (or website domain) and their title matches a target role as a contiguous phrase. No emails are collected. “No match” stays “no match”.</Callout>
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full min-w-[44rem] text-left text-sm" data-testid="buyers-table">
          <thead className="bg-surface-2 text-xs text-muted"><tr><th className="px-4 py-2.5">Account</th><th>Contact</th><th>Title</th><th>Role matched</th><th>Employer check</th><th className="pr-4">Flags</th></tr></thead>
          <tbody>{searched.flatMap((a) => {
            const ps = m.people[a.company_id ?? ""] ?? [];
            if (ps.length === 0) return [<tr key={a.name} className="border-t border-border text-muted"><td className="px-4 py-2.5 font-medium text-text">{a.name}</td><td colSpan={5}><Badge tone="warn">buyer not found</Badge> no verified contact in the target roles</td></tr>];
            return ps.map((p, i) => (
              <tr key={`${a.name}${p.person_id}`} className="border-t border-border align-top">
                <td className="px-4 py-2.5 font-medium">{i === 0 ? a.name : ""}</td><td>{p.name}</td><td className="text-muted">{p.current_title ?? UNKNOWN}</td>
                <td>{p.role_matched ? <Badge tone="brand">{p.role_matched}</Badge> : UNKNOWN}</td>
                <td><Badge tone="good">verified · {p.verification_method}</Badge></td><td className="pr-4 text-xs text-warn">{p.missing_flags.filter((f) => f !== "linkedin_url_missing").join(", ")}</td>
              </tr>));
          })}</tbody>
        </table>
      </div>
      {notSearched > 0 && <p className="text-xs text-muted">{notSearched} shortlisted account(s) were not searched (search stops once enough accounts have verified buyers).</p>}
    </div>
  );
}

const CLS: Record<Competitor["classification"], { tone: Tone; label: string; help: string }> = {
  confirmed: { tone: "bad", label: "Confirmed competitor", help: "Description matches your product category AND an independent web result mentions the company." },
  possible: { tone: "warn", label: "Possible competitor", help: "Either the description matches the category or the web mentions it, but not both." },
  insufficient_evidence: { tone: "neutral", label: "Insufficient evidence", help: "Neither signal is present." },
};
export function Competitors({ list }: { list: Competitor[] }) {
  if (list.length === 0) return <Empty title="No competitor data">The competitor scan did not return results for this run.</Empty>;
  return (
    <div className="space-y-3">
      <Callout tone="neutral" title="Conservative by design">Positioning text is the provider&apos;s company description, not a verified claim. Differentiators and pricing are not assessed or inferred.</Callout>
      <div className="grid gap-3 md:grid-cols-2" data-testid="competitors">{list.map((c) => (
        <Card key={c.company_id ?? c.name} className="p-4">
          <div className="flex items-start justify-between gap-2"><div><div className="font-semibold">{c.name}</div>
            {c.domain && <a className="inline-flex items-center gap-1 text-xs text-brand underline" href={`https://${c.domain}`} target="_blank" rel="noreferrer noopener">{c.domain}<ExternalLink size={11} /></a>}</div>
            <Badge tone={CLS[c.classification].tone} title={CLS[c.classification].help}>{CLS[c.classification].label}</Badge></div>
          <p className="mt-2 text-sm text-muted">{c.positioning_claim ? `“${c.positioning_claim}”` : UNKNOWN}</p>
          <div className="mt-2 text-xs text-muted">{num(c.employee_count)} people · {c.evidence_ids.length} evidence records</div>
        </Card>))}</div>
    </div>
  );
}

const SRC: Record<Source, Tone> = { user: "good", inferred: "brand", defaulted: "warn" };
export function Assumptions({ m }: { m: Mission }) {
  const b = m.brief!;
  return (
    <div className="space-y-3">
      {b.unsupported_constraints.length > 0 && <Callout tone="warn" title="Constraints that could not be applied">{b.unsupported_constraints.join("; ")}</Callout>}
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full text-left text-sm"><thead className="bg-surface-2 text-xs text-muted"><tr><th className="px-4 py-2.5">Field</th><th>Value</th><th>Source</th><th className="pr-4">Note</th></tr></thead>
          <tbody>{b.assumptions.map((a, i) => (
            <tr key={i} className="border-t border-border align-top"><td className="px-4 py-2 font-medium">{a.field}</td>
              <td className="font-mono text-xs">{a.value == null ? <span className="text-warn">unknown</span> : Array.isArray(a.value) ? a.value.join(", ") : String(a.value)}</td>
              <td><Badge tone={SRC[a.source]}>{a.source}</Badge></td><td className="pr-4 text-xs text-muted">{a.note}</td></tr>))}</tbody></table>
      </div>
    </div>
  );
}

export function EvidenceExplorer({ missionId, total }: { missionId: string; total: number }) {
  const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [sel, setSel] = useState<string | null>(null);
  const r = useQuery({ queryKey: ["evidence", missionId, q, status], queryFn: () => api.evidence(missionId, { q, status, limit: 100 }) });
  const cls = "rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input aria-label="Search evidence" data-testid="evidence-search" className={cls} placeholder="Search claims or field paths" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Status" className={cls} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Any status</option>{["supported", "unsupported", "unverified", "stale", "conflicting"].map((s) => <option key={s}>{s}</option>)}</select>
        <span className="ml-auto text-xs text-muted">{r.data ? `${r.data.items.length} of ${r.data.total} shown` : ""} · {total} claims in this mission</span>
      </div>
      {r.isLoading ? <Skeleton className="h-48" /> : (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full min-w-[48rem] text-left text-sm" data-testid="evidence-table"><thead className="bg-surface-2 text-xs text-muted"><tr><th className="px-4 py-2.5">ID</th><th>Claim</th><th>Field path</th><th>Retrieved</th><th className="pr-4">Status</th></tr></thead>
            <tbody>{r.data?.items.map((e) => (
              <tr key={e.evidence_id} tabIndex={0} role="button" className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => setSel(e.evidence_id)} onKeyDown={(ev) => ev.key === "Enter" && setSel(e.evidence_id)}>
                <td className="px-4 py-2 font-mono text-xs">{e.evidence_id}</td><td>{e.claim}</td><td className="font-mono text-xs text-muted">{e.field_path ?? "–"}</td>
                <td className="text-xs text-muted">{new Date(e.retrieved_at_utc).toLocaleTimeString()}</td><td className="pr-4"><Badge tone={statusTone(e.status)}>{e.status}</Badge></td></tr>))}</tbody></table>
        </div>)}
      <Drawer open={!!sel} onClose={() => setSel(null)} title={`Evidence ${sel ?? ""}`} width="max-w-xl">{sel && <SourceViewer missionId={missionId} evidenceId={sel} />}</Drawer>
    </div>
  );
}

const FILES: Record<string, { label: string; desc: string; icon: typeof FileText }> = {
  "Market_Entry_Report.pdf": { label: "Market entry report (PDF)", desc: "Executive recommendation, segmentation, competitors, sizing, assumptions, risks, launch plan.", icon: FileText },
  "Market_Entry_Report.html": { label: "Report (HTML)", desc: "Same report; opens in any browser.", icon: FileText },
  "Target_Accounts.csv": { label: "Target accounts (CSV)", desc: "Ranked accounts with IDs, scores, coverage, verification and evidence refs.", icon: FileSpreadsheet },
  "Buyer_Map.csv": { label: "Buyer map (CSV)", desc: "Verified people with employer linkage; no emails.", icon: FileSpreadsheet },
  "Competitive_Landscape.csv": { label: "Competitive landscape (CSV)", desc: "Competitors with classification and evidence links.", icon: FileSpreadsheet },
  "Evidence_Log.json": { label: "Evidence log (JSON)", desc: "Every claim: source, field path, timestamp, status, contradictions, plus all API calls.", icon: FileJson },
};
export function Exports({ m }: { m: Mission }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2" data-testid="exports">
        {m.artifacts.filter((n) => FILES[n]).map((n) => {
          const f = FILES[n];
          return (
            <Card key={n} className="flex items-start gap-3 p-4"><f.icon className="mt-0.5 text-brand" size={20} />
              <div className="flex-1"><div className="text-sm font-semibold">{f.label}</div><p className="text-xs text-muted">{f.desc}</p></div>
              <a href={api.artifactUrl(m.mission_id, n)} download className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-surface-2"><Download size={14} />Download</a></Card>);
        })}
      </div>
      <Card className="flex items-center gap-3 p-4"><Kanban className="text-brand" size={20} />
        <div className="flex-1"><div className="text-sm font-semibold">Local CRM</div><p className="text-xs text-muted">{m.crm_counts.companies ?? 0} accounts · {m.crm_counts.people ?? 0} contacts · {m.crm_counts.unsent_drafts ?? 0} unsent drafts · {m.crm_counts.crm_tasks ?? 0} tasks</p></div>
        <Link href={`/missions/${m.mission_id}/crm`} className="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white dark:text-[#0d1117]">Open CRM board</Link></Card>
    </div>
  );
}

export type { Account };
