"use client";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, EmptyState, Pill, inputBase, inputCls, td, th } from "@/components/ui";
import { CONTACT, num, priority } from "@/lib/format";
import type { Account } from "@/lib/types";

type Sort = "score" | "size" | "growth" | "name";
const sorters: Record<Sort, (a: Account, b: Account) => number> = {
  score: (a, b) => a.rank - b.rank, size: (a, b) => (b.employee_count ?? -1) - (a.employee_count ?? -1),
  growth: (a, b) => (b.headcount_growth_6m ?? -1e9) - (a.headcount_growth_6m ?? -1e9), name: (a, b) => a.name.localeCompare(b.name),
};

export function Companies({ accounts, onOpen }: { accounts: Account[]; onOpen: (id: string) => void }) {
  const [q, setQ] = useState(""); const [prio, setPrio] = useState("all"); const [contact, setContact] = useState("all"); const [sort, setSort] = useState<Sort>("score");
  const rows = useMemo(() => accounts.filter((a) => (prio === "all" || a.wave === prio) && (contact === "all" || a.buyer_status === contact)
    && (!q || `${a.name} ${a.domain ?? ""}`.toLowerCase().includes(q.toLowerCase()))).sort(sorters[sort]), [accounts, q, prio, contact, sort]);
  const sel = `${inputBase} w-auto`;
  return (
    <div className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <div className="relative w-full max-w-xs"><Search size={14} className="absolute left-3 top-2.5 text-muted" /><input aria-label="Search companies" data-testid="account-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search companies" className={`${inputCls} pl-8`} /></div>
        <select aria-label="Priority" className={sel} value={prio} onChange={(e) => setPrio(e.target.value)}><option value="all">All priorities</option><option value="Wave 1">Contact first</option><option value="Wave 2">Next in line</option><option value="Research Needed">Needs research</option></select>
        <select aria-label="Decision-maker" className={sel} value={contact} onChange={(e) => setContact(e.target.value)}><option value="all">Any decision-maker status</option><option value="found">Decision-maker found</option><option value="buyer_not_found">None found</option><option value="not_searched">Not searched</option></select>
        <select aria-label="Sort by" className={sel} value={sort} onChange={(e) => setSort(e.target.value as Sort)}><option value="score">Sort: best match</option><option value="size">Sort: largest</option><option value="growth">Sort: fastest growing</option><option value="name">Sort: name</option></select>
        <span className="ml-auto text-[13px] text-muted">{rows.length} of {accounts.length}</span>
      </div>
      {rows.length === 0 ? <div className="p-6"><EmptyState title="No companies match these filters" /></div> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] text-sm" data-testid="accounts-table">
            <thead className="border-b border-line"><tr><th className={th}>Company</th><th className={`${th} text-right`}>Employees</th><th className={`${th} text-right`}>Growth (6 mo)</th><th className={`${th} text-right`}>Open jobs</th><th className={`${th} w-40`}>Match</th><th className={th}>Priority</th><th className={th}>Decision-maker</th></tr></thead>
            <tbody>{rows.map((a) => {
              const p = priority(a.wave); const c = CONTACT[a.buyer_status];
              return (
                <tr key={a.company_id ?? a.name} tabIndex={0} onClick={() => a.company_id && onOpen(a.company_id)} onKeyDown={(e) => e.key === "Enter" && a.company_id && onOpen(a.company_id)}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-subtle" data-testid="account-row">
                  <td className={td}><div className="font-medium text-ink">{a.name}</div><div className="text-[13px] text-muted">{a.domain ?? "No website"}</div></td>
                  <td className={`${td} tabular text-right`}>{num(a.employee_count)}</td>
                  <td className={`${td} tabular text-right ${a.headcount_growth_6m == null ? "text-muted" : a.headcount_growth_6m > 0 ? "text-ok" : a.headcount_growth_6m < 0 ? "text-bad" : ""}`}>{a.headcount_growth_6m == null ? "—" : `${a.headcount_growth_6m > 0 ? "+" : ""}${a.headcount_growth_6m.toFixed(1)}%`}</td>
                  <td className={`${td} tabular text-right ${a.open_roles == null ? "text-muted" : ""}`} title={a.open_roles == null ? "No job postings tracked for this company" : undefined}>{a.open_roles ?? "—"}</td>
                  <td className={td}><div className="flex items-center gap-2.5"><Bar value={a.fit_score} tone={(a.fit_score ?? 0) >= 60 ? "ok" : "accent"} /><span className="tabular w-7 text-right font-medium">{a.fit_score ?? "—"}</span></div></td>
                  <td className={td}><Pill tone={p.tone}>{p.label}</Pill></td>
                  <td className={td}><Pill tone={c.tone} dot={false}>{c.label}</Pill></td>
                </tr>);
            })}</tbody>
          </table>
        </div>)}
    </div>
  );
}
