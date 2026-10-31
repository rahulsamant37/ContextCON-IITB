"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Kanban, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Accounts } from "@/components/results/accounts";
import { Overview } from "@/components/results/overview";
import { Assumptions, Buyers, Competitors, EvidenceExplorer, Exports } from "@/components/results/tabs-misc";
import { Badge, Button, Callout, Skeleton, Tabs, type Tone } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { ago, STATE_LABEL } from "@/lib/format";

type Tab = "overview" | "accounts" | "buyers" | "competitors" | "assumptions" | "evidence" | "exports";
const STATE_TONE: Record<string, Tone> = { completed: "good", completed_with_warnings: "warn", partial: "warn", failed: "bad" };

export default function MissionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const q = useQuery({ queryKey: ["mission", id], queryFn: () => api.mission(id), retry: false });
  const rerun = useMutation({
    mutationFn: () => api.create(q.data!.brief!.raw_prompt, { replay: false, simulate_failure: false, use_llm: true }),
    onSuccess: (r) => router.push(`/missions/${r.mission_id}/run`),
  });
  useEffect(() => { if (q.error instanceof ApiError && q.error.status === 409) router.replace(`/missions/${id}/run`); }, [q.error, id, router]);

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-28" /><Skeleton className="h-64" /></div>;
  if (q.error || !q.data) return <Callout tone="bad" title="Could not load this mission">{(q.error as Error | null)?.message ?? "Unknown error"} <Link className="underline" href="/history">Back to missions</Link></Callout>;
  const m = q.data;
  const b = m.brief;

  if (!b || m.state === "failed") {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Callout tone="bad" title="This mission could not complete">Nothing was fabricated to fill the gap. Here is why:</Callout>
        <ul className="list-disc space-y-1 pl-6 text-sm" data-testid="failure-reasons">{m.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        <Link href="/"><Button>Try a different request</Button></Link>
      </div>
    );
  }
  const people = Object.values(m.people).reduce((n, v) => n + v.length, 0);
  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold" data-testid="mission-title">{b.target_industry} in {b.target_country}</h1>
            <Badge tone={STATE_TONE[m.state]}>{STATE_LABEL[m.state]}</Badge>
          </div>
          <p className="mt-1 max-w-3xl text-sm text-muted">{b.product_description} · {b.employee_min ?? "any"}–{b.employee_max ?? "any"} employees · {ago(m.finished_at ?? m.started_at)}</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/missions/${id}/crm`}><Button variant="secondary" data-testid="open-crm"><Kanban size={16} />CRM board</Button></Link>
          <Button variant="ghost" disabled={rerun.isPending} onClick={() => rerun.mutate()} title="Run the same request again with fresh data"><RefreshCw size={16} />Re-run</Button>
        </div>
      </div>
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "overview", label: "Overview" }, { id: "accounts", label: "Accounts", count: m.accounts.length }, { id: "buyers", label: "Buyers", count: people },
        { id: "competitors", label: "Competitors", count: m.competitors.length }, { id: "assumptions", label: "Assumptions" },
        { id: "evidence", label: "Evidence", count: m.verification?.checked }, { id: "exports", label: "Exports & CRM" }]} />
      <div className="pt-5">
        {tab === "overview" && <Overview m={m} />}
        {tab === "accounts" && <Accounts missionId={id} accounts={m.accounts} />}
        {tab === "buyers" && <Buyers m={m} />}
        {tab === "competitors" && <Competitors list={m.competitors} />}
        {tab === "assumptions" && <Assumptions m={m} />}
        {tab === "evidence" && <EvidenceExplorer missionId={id} total={m.verification?.checked ?? 0} />}
        {tab === "exports" && <Exports m={m} />}
      </div>
    </div>
  );
}
