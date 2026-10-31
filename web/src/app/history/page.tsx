"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Badge, Card, Empty, Skeleton, type Tone } from "@/components/ui";
import { api } from "@/lib/api";
import { ago, money, num, STATE_LABEL } from "@/lib/format";

const TONE: Record<string, Tone> = { completed: "good", completed_with_warnings: "warn", partial: "warn", failed: "bad" };

export default function History() {
  const q = useQuery({ queryKey: ["history"], queryFn: api.list, refetchInterval: (s) => (s.state.data?.running.length ? 3000 : false) });
  if (q.isLoading) return <Skeleton className="h-64" />;
  const { running = [], missions = [] } = q.data ?? {};
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Missions</h1>
      <p className="mb-5 text-sm text-muted">Every mission is saved with its evidence and CRM rows. Re-running the same request updates it, never duplicates it.</p>
      {running.map((r) => (
        <Link key={r.mission_id} href={`/missions/${r.mission_id}/run`}><Card className="mb-3 flex items-center gap-3 p-4 hover:bg-surface-2"><span className="pulse-dot h-2.5 w-2.5 rounded-full bg-brand" /><div className="min-w-0 flex-1 truncate text-sm">{r.prompt}</div><Badge tone="brand">{r.status}</Badge></Card></Link>))}
      {missions.length === 0 && running.length === 0 ? <Empty title="No missions yet" action={<Link href="/" className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white dark:text-[#0d1117]">Start your first mission</Link>}>Describe a product and a target market to get your first research packet.</Empty> : (
        <div className="space-y-3" data-testid="history-list">{missions.map((s) => (
          <Link key={s.mission_id} href={`/missions/${s.mission_id}`}>
            <Card className="mb-3 p-4 hover:bg-surface-2">
              <div className="flex flex-wrap items-center gap-2"><div className="font-semibold">{s.industry ?? "?"} in {s.country ?? "?"}</div><Badge tone={TONE[s.state]}>{STATE_LABEL[s.state]}</Badge><span className="ml-auto text-xs text-muted">{ago(s.created_at)}</span></div>
              <p className="mt-1 line-clamp-1 text-sm text-muted">{s.product ?? s.prompt}</p>
              <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted"><span>{num(s.indexed_count)} indexed</span><span>{s.accounts} accounts · {s.wave1} Wave 1</span>{s.pool != null && <span>pool {money(s.pool, s.currency)}</span>}<span>{s.credits != null ? `${s.credits.toFixed(1)} credits` : ""}</span></div>
            </Card></Link>))}</div>)}
    </div>
  );
}
