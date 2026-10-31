"use client";
import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, FileSpreadsheet, FileText, Search } from "lucide-react";
import { useState } from "react";
import { Card, CardHeader, EmptyState, LinkButton, Notice, Pill, SidePanel, Skeleton, inputBase, inputCls, td, th } from "@/components/ui";
import { api } from "@/lib/api";
import { COMPETITOR, num, SOURCE_STATUS } from "@/lib/format";
import type { Mission } from "@/lib/types";
import { SourceViewer } from "./source-viewer";

export function DecisionMakers({ m, onOpen }: { m: Mission; onOpen: (id: string) => void }) {
  const rows = m.accounts.flatMap((a) => (m.people[a.company_id ?? ""] ?? []).map((p) => ({ a, p })));
  const none = m.accounts.filter((a) => a.buyer_status === "buyer_not_found");
  if (rows.length === 0 && none.length === 0) return <EmptyState title="No decision-makers searched">Decision-maker search didn&apos;t run for this research. See “Things to keep in mind” on the overview.</EmptyState>;
  return (
    <div className="space-y-4">
      <p className="text-[13px] text-muted">We only list people whose job title matches your buyer roles and whose current employer matches the company. We don&apos;t collect email addresses.</p>
      <div className="overflow-x-auto rounded-lg border border-line bg-surface">
        <table className="w-full min-w-[40rem] text-sm" data-testid="buyers-table">
          <thead className="border-b border-line"><tr><th className={th}>Name</th><th className={th}>Title</th><th className={th}>Company</th><th className={th}>Role</th><th className={th}>Employer</th></tr></thead>
          <tbody>{rows.map(({ a, p }) => (
            <tr key={`${a.company_id}-${p.person_id}`} className="border-b border-line last:border-0">
              <td className={`${td} font-medium`}>{p.name}</td><td className={`${td} text-ink-2`}>{p.current_title ?? "—"}</td>
              <td className={td}><button className="text-accent hover:underline" onClick={() => a.company_id && onOpen(a.company_id)}>{a.name}</button></td>
              <td className={td}>{p.role_matched ?? "—"}</td><td className={td}><Pill tone="ok">Confirmed</Pill></td></tr>))}</tbody>
        </table>
      </div>
      {none.length > 0 && <Notice tone="neutral" title={`No decision-maker found at ${none.length} compan${none.length === 1 ? "y" : "ies"}`}>{none.map((a) => a.name).join(", ")}. These stay in your pipeline as “find a contact” tasks.</Notice>}
    </div>
  );
}

export function Competitors({ m }: { m: Mission }) {
  if (m.competitors.length === 0) return <EmptyState title="No competitors found">The competitor search returned no results for this product description.</EmptyState>;
  return (
    <div className="space-y-4">
      <p className="text-[13px] text-muted">“Direct competitor” means the company describes a similar product and is also mentioned in independent web results. Descriptions are each company&apos;s own words.</p>
      <div className="grid gap-4 md:grid-cols-2" data-testid="competitors">{m.competitors.map((c) => {
        const k = COMPETITOR[c.classification];
        return (
          <Card key={c.company_id ?? c.name} className="p-5">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="font-medium text-ink">{c.name}</div>
              {c.domain && <a className="inline-flex items-center gap-1 text-[13px] text-muted hover:text-ink" href={`https://${c.domain}`} target="_blank" rel="noreferrer noopener">{c.domain}<ExternalLink size={11} /></a>}</div>
              <Pill tone={k.tone} title={k.help}>{k.label}</Pill></div>
            <p className="mt-3 line-clamp-3 text-[13px] leading-relaxed text-ink-2">{c.positioning_claim ?? "No description available."}</p>
            <div className="mt-3 text-xs text-muted">{c.employee_count != null ? `${num(c.employee_count)} employees` : "Size not available"}</div>
          </Card>);
      })}</div>
    </div>
  );
}

export function Sources({ missionId, total, fraction }: { missionId: string; total: number; fraction: number | null }) {
  const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [sel, setSel] = useState<string | null>(null);
  const r = useQuery({ queryKey: ["evidence", missionId, q, status], queryFn: () => api.evidence(missionId, { q, status, limit: 100 }) });
  return (
    <div className="space-y-4">
      <Notice tone="ok" title={`${total.toLocaleString()} facts, ${fraction != null ? Math.round(fraction * 100) : "—"}% confirmed against the original data`}>Every number in this research links to the exact record it came from. Click a fact to see it.</Notice>
      <div className="rounded-lg border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <div className="relative w-full max-w-xs"><Search size={14} className="absolute left-3 top-2.5 text-muted" /><input aria-label="Search facts" data-testid="evidence-search" className={`${inputCls} pl-8`} placeholder="Search facts, e.g. funding" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <select aria-label="Status" className={`${inputBase} w-auto`} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{Object.entries(SOURCE_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select>
          <span className="ml-auto text-[13px] text-muted">{r.data ? `Showing ${r.data.items.length} of ${r.data.total}` : ""}</span>
        </div>
        {r.isLoading ? <div className="p-4"><Skeleton className="h-40" /></div> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm" data-testid="evidence-table">
              <thead className="border-b border-line"><tr><th className={th}>Fact</th><th className={th}>Status</th><th className={th}>Retrieved</th></tr></thead>
              <tbody>{r.data?.items.map((e) => (
                <tr key={e.evidence_id} tabIndex={0} className="cursor-pointer border-b border-line last:border-0 hover:bg-subtle" onClick={() => setSel(e.evidence_id)} onKeyDown={(ev) => ev.key === "Enter" && setSel(e.evidence_id)}>
                  <td className={`${td} max-w-xl truncate`}>{e.claim}</td><td className={td}><Pill tone={SOURCE_STATUS[e.status]?.tone}>{SOURCE_STATUS[e.status]?.label}</Pill></td>
                  <td className={`${td} whitespace-nowrap text-[13px] text-muted`}>{new Date(e.retrieved_at_utc).toLocaleString()}</td></tr>))}</tbody>
            </table>
          </div>)}
      </div>
      <SidePanel open={!!sel} onClose={() => setSel(null)} title="Source">{sel && <SourceViewer missionId={missionId} evidenceId={sel} />}</SidePanel>
    </div>
  );
}

const SRC_LABEL: Record<string, { label: string; tone: "ok" | "info" | "warn" }> = { user: { label: "From you", tone: "ok" }, inferred: { label: "Inferred", tone: "info" }, defaulted: { label: "Default", tone: "warn" } };
const FIELD_LABEL: Record<string, string> = {
  target_country: "Country", target_industry: "Industry", product_description: "Product", target_buyer_roles: "Buyer roles", competitor_keywords: "Competitor search terms",
  employee_min: "Minimum employees", employee_max: "Maximum employees", annual_contract_value: "Annual contract value", "taxonomy.categories": "Matched industry categories",
  product_name: "Product name", currency: "Currency",
};
export function Brief({ m }: { m: Mission }) {
  const b = m.brief!;
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader title="Your brief" />
        <dl className="divide-y divide-line text-sm">{[
          ["Product", b.product_description], ["Country", b.target_country], ["Industry", b.target_industry],
          ["Company size", b.employee_min != null || b.employee_max != null ? `${b.employee_min ?? "any"}–${b.employee_max ?? "any"} employees` : "Any size"],
          ["Annual contract value", b.annual_contract_value != null ? `${b.currency ?? ""} ${b.annual_contract_value.toLocaleString()}` : "Not provided"],
          ["Buyer roles", b.target_buyer_roles.join(", ")]].map(([k, v]) => (
            <div key={k} className="grid grid-cols-[11rem_1fr] gap-3 px-5 py-3"><dt className="text-muted">{k}</dt><dd className="text-ink">{v}</dd></div>))}</dl>
        {b.raw_prompt && <p className="border-t border-line px-5 py-3 text-[13px] text-muted">“{b.raw_prompt}”</p>}
      </Card>
      <Card>
        <CardHeader title="How we interpreted it" description="Where each setting came from. Defaults are shown so nothing is hidden." />
        <ul className="divide-y divide-line text-sm">{b.assumptions.filter((a) => FIELD_LABEL[a.field]).map((a, i) => (
          <li key={i} className="flex items-start justify-between gap-3 px-5 py-3"><div className="min-w-0"><div className="text-ink">{FIELD_LABEL[a.field]}</div>
            <div className="truncate text-[13px] text-muted">{a.value == null ? "Not set" : Array.isArray(a.value) ? a.value.join(", ") : String(a.value)}</div></div>
            <Pill tone={SRC_LABEL[a.source].tone} dot={false}>{SRC_LABEL[a.source].label}</Pill></li>))}</ul>
        {b.unsupported_constraints.length > 0 && <div className="border-t border-line p-4"><Notice tone="warn" title="Couldn't apply">{b.unsupported_constraints.join("; ")}</Notice></div>}
      </Card>
    </div>
  );
}

const FILES: Record<string, { label: string; desc: string; pdf?: boolean }> = {
  "Market_Entry_Report.pdf": { label: "Market entry report", desc: "Recommendation, target companies, competitors, market value, assumptions and next steps.", pdf: true },
  "Target_Accounts.csv": { label: "Target companies", desc: "Spreadsheet of ranked companies with scores and sources." },
  "Buyer_Map.csv": { label: "Decision-makers", desc: "People in your buyer roles with confirmed employers." },
  "Competitive_Landscape.csv": { label: "Competitors", desc: "Competitors with descriptions and how sure we are." },
  "Evidence_Log.json": { label: "Source log", desc: "Every fact with its source, for audits (JSON)." },
  "Market_Entry_Report.html": { label: "Report (web page)", desc: "The same report as a web page.", pdf: true },
};
export function Downloads({ m }: { m: Mission }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card>
        <ul className="divide-y divide-line" data-testid="exports">{Object.entries(FILES).filter(([n]) => m.artifacts.includes(n)).map(([n, f]) => (
          <li key={n} className="flex items-center gap-4 px-5 py-4">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-subtle text-ink-2">{f.pdf ? <FileText size={18} /> : <FileSpreadsheet size={18} />}</div>
            <div className="min-w-0 flex-1"><div className="text-sm font-medium text-ink">{f.label}</div><div className="text-[13px] text-muted">{f.desc}</div></div>
            <a href={api.artifactUrl(m.mission_id, n)} download className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong px-3 text-[13px] font-medium hover:bg-subtle"><Download size={14} />{n.split(".").pop()?.toUpperCase()}</a>
          </li>))}</ul>
      </Card>
      <Card className="p-5">
        <div className="text-sm font-semibold">Your sales pipeline</div>
        <p className="mt-1 text-[13px] text-muted">{m.crm_counts.companies ?? 0} companies, {m.crm_counts.people ?? 0} decision-makers and {m.crm_counts.unsent_drafts ?? 0} draft messages are ready. Nothing has been sent.</p>
        <LinkButton href={`/missions/${m.mission_id}/crm`} className="mt-4 w-full" variant="secondary">Open pipeline</LinkButton>
      </Card>
    </div>
  );
}
