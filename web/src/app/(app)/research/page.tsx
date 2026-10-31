"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { EmptyState, LinkButton, Notice, PageHeader, Pill, Skeleton, inputCls, td, th } from "@/components/ui";
import { api } from "@/lib/api";
import { ago, money, num, STATE } from "@/lib/format";

function ResearchListInner() {
  const router = useRouter();
  const q = useQuery({ queryKey: ["history"], queryFn: api.list, refetchInterval: (s) => (s.state.data?.running.length ? 3000 : false) });
  const [filter, setFilter] = useState("");
  const rows = useMemo(() => (q.data?.missions ?? []).filter((m) => !filter || `${m.industry} ${m.country} ${m.product}`.toLowerCase().includes(filter.toLowerCase())), [q.data, filter]);

  return (
    <>
      <PageHeader title="Research" description="Each research project studies one market: who to sell to, who decides, who you compete with and what the market is worth."
        actions={<LinkButton href="/research/new" data-testid="new-research">New research</LinkButton>} />

      {q.isError && <Notice tone="bad" title="Can't reach the MarketEntry server">Start it with <code className="rounded bg-surface px-1">scripts/dev.sh</code>, then refresh this page.</Notice>}

      {q.data?.running.map((r) => (
        <button key={r.mission_id} onClick={() => router.push(`/research/${r.mission_id}/run`)} className="mb-4 flex w-full items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3 text-left hover:bg-subtle">
          <Loader2 size={16} className="animate-spin text-accent" /><div className="min-w-0 flex-1"><div className="text-sm font-medium">Research in progress</div><div className="truncate text-[13px] text-muted">{r.prompt}</div></div>
          <span className="flex items-center gap-1 text-[13px] font-medium text-ink">View progress<ArrowRight size={14} /></span></button>))}

      {q.isLoading ? <div className="space-y-2"><Skeleton className="h-10" /><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
        : rows.length === 0 && !filter ? (
          <EmptyState title="Welcome! Let's research your first market" icon={<Search size={28} />}
            action={<div className="flex flex-wrap justify-center gap-2"><LinkButton href="/research/new?example=germany" data-testid="welcome-demo">Run the free demo</LinkButton><LinkButton href="/research/new" variant="secondary">Research my market</LinkButton></div>}>
            Tell us what you sell and which market you are considering. In about a minute you get a ranked list of target companies, the people to talk to, competitors and an estimate of the market&apos;s value.
          </EmptyState>
        ) : (
          <div className="rounded-lg border border-line bg-surface">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div className="relative w-full max-w-xs"><Search size={14} className="absolute left-3 top-2.5 text-muted" /><input aria-label="Filter research" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by market or product" className={`${inputCls} pl-8`} /></div>
              <span className="text-[13px] text-muted">{rows.length} project{rows.length === 1 ? "" : "s"}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[46rem] text-sm" data-testid="history-list">
                <thead className="border-b border-line"><tr><th className={th}>Market</th><th className={th}>Status</th><th className={`${th} text-right`}>Companies found</th><th className={`${th} text-right`}>Contact first</th><th className={`${th} text-right`}>Market value</th><th className={th}>Created</th></tr></thead>
                <tbody>{rows.map((m) => (
                  <tr key={m.mission_id} onClick={() => router.push(`/research/${m.mission_id}`)} onKeyDown={(e) => e.key === "Enter" && router.push(`/research/${m.mission_id}`)} tabIndex={0} className="cursor-pointer border-b border-line last:border-0 hover:bg-subtle">
                    <td className={td}><div className="font-medium text-ink">{m.industry && m.industry !== "unknown" ? `${m.industry} in ${m.country}` : "Unrecognised request"}</div><div className="max-w-md truncate text-[13px] text-muted">{m.product}</div></td>
                    <td className={td}><Pill tone={STATE[m.state]?.tone ?? "neutral"}>{STATE[m.state]?.label ?? m.state}</Pill></td>
                    <td className={`${td} tabular text-right`}>{num(m.indexed_count)}</td>
                    <td className={`${td} tabular text-right`}>{m.wave1}</td>
                    <td className={`${td} tabular text-right`}>{m.pool != null ? money(m.pool, m.currency, true) : <span className="text-muted">—</span>}</td>
                    <td className={`${td} text-muted`}>{ago(m.created_at)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          </div>)}
    </>
  );
}

export default function ResearchList() {
  return <Suspense fallback={null}><ResearchListInner /></Suspense>;
}
