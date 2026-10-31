"use client";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, Empty, Meter, statusTone, waveTone } from "@/components/ui";
import { num, pct, UNKNOWN } from "@/lib/format";
import type { Account } from "@/lib/types";
import { AccountDrawer } from "./account-drawer";

type SortKey = "rank" | "fit" | "headcount" | "growth";
const sorters: Record<SortKey, (a: Account, b: Account) => number> = {
  rank: (a, b) => a.rank - b.rank,
  fit: (a, b) => (b.fit_score ?? -1) - (a.fit_score ?? -1),
  headcount: (a, b) => (b.employee_count ?? -1) - (a.employee_count ?? -1),
  growth: (a, b) => (b.headcount_growth_6m ?? -1e9) - (a.headcount_growth_6m ?? -1e9),
};

export function Accounts({ missionId, accounts }: { missionId: string; accounts: Account[] }) {
  const [q, setQ] = useState(""); const [wave, setWave] = useState("all"); const [buyer, setBuyer] = useState("all"); const [sort, setSort] = useState<SortKey>("rank");
  const [sel, setSel] = useState<string | null>(null);
  const rows = useMemo(() => accounts
    .filter((a) => (wave === "all" || a.wave === wave || (wave === "out" && !a.wave)) && (buyer === "all" || a.buyer_status === buyer)
      && (!q || `${a.name} ${a.domain ?? ""}`.toLowerCase().includes(q.toLowerCase())))
    .sort(sorters[sort]), [accounts, q, wave, buyer, sort]);
  const sel_ = "rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-muted" /><input aria-label="Search accounts" data-testid="account-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search company or domain" className={`${sel_} pl-8`} /></div>
        <select aria-label="Wave" className={sel_} value={wave} onChange={(e) => setWave(e.target.value)}><option value="all">All waves</option><option>Wave 1</option><option>Wave 2</option><option>Research Needed</option><option value="out">Out of ICP</option></select>
        <select aria-label="Buyer status" className={sel_} value={buyer} onChange={(e) => setBuyer(e.target.value)}><option value="all">Any buyer status</option><option value="found">Buyer found</option><option value="buyer_not_found">Buyer not found</option><option value="not_searched">Not searched</option></select>
        <select aria-label="Sort" className={sel_} value={sort} onChange={(e) => setSort(e.target.value as SortKey)}><option value="rank">Rank</option><option value="fit">Fit score</option><option value="headcount">Headcount</option><option value="growth">Growth</option></select>
        <span className="ml-auto text-xs text-muted">{rows.length} of {accounts.length} accounts</span>
      </div>
      {rows.length === 0 ? <Empty title="No accounts match these filters" /> : (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full min-w-[56rem] text-left text-sm" data-testid="accounts-table">
            <thead className="bg-surface-2 text-xs text-muted"><tr>
              <th className="px-4 py-2.5">#</th><th>Company</th><th>Headcount</th><th>6m growth</th><th>Open roles</th><th className="w-32">Fit</th><th className="w-28">Coverage</th><th>Wave</th><th>Buyer</th><th className="pr-4">Verified</th></tr></thead>
            <tbody>{rows.map((a) => (
              <tr key={a.company_id ?? a.name} tabIndex={0} role="button" onClick={() => a.company_id && setSel(a.company_id)} onKeyDown={(e) => e.key === "Enter" && a.company_id && setSel(a.company_id)}
                className="cursor-pointer border-t border-border hover:bg-surface-2" data-testid="account-row">
                <td className="px-4 py-2.5 text-muted">{a.rank}</td>
                <td><div className="font-medium">{a.name}</div><div className="text-xs text-muted">{a.domain ?? UNKNOWN}</div></td>
                <td className="tabular-nums">{num(a.employee_count)}</td>
                <td className="tabular-nums">{a.headcount_growth_6m == null ? <span className="text-warn">unknown</span> : pct(a.headcount_growth_6m)}</td>
                <td className="tabular-nums">{a.open_roles == null ? <span className="text-warn" title="Provider tracks no postings: not the same as zero">unknown</span> : a.open_roles}</td>
                <td><div className="flex items-center gap-2"><Meter value={a.fit_score} tone={(a.fit_score ?? 0) >= 60 ? "good" : "brand"} /><span className="w-9 text-right text-xs tabular-nums">{a.fit_score ?? "–"}</span></div></td>
                <td><div className="flex items-center gap-2"><Meter value={a.data_coverage * 100} tone="neutral" /><span className="w-9 text-xs tabular-nums text-muted">{Math.round(a.data_coverage * 100)}%</span></div></td>
                <td><Badge tone={waveTone(a.wave)}>{a.wave ?? "out of ICP"}</Badge></td>
                <td><Badge tone={a.buyer_status === "found" ? "good" : a.buyer_status === "buyer_not_found" ? "warn" : "neutral"}>{a.buyer_status.replaceAll("_", " ")}</Badge></td>
                <td className="pr-4"><Badge tone={statusTone(a.verification_status)}>{a.verification_status}</Badge></td>
              </tr>))}</tbody>
          </table>
        </div>)}
      <AccountDrawer missionId={missionId} companyId={sel} onClose={() => setSel(null)} />
    </div>
  );
}
