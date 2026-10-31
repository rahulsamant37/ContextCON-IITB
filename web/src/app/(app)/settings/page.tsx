"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, Notice, PageHeader, Pill, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

const LIMITS: Record<string, [string, string]> = {
  max_credits_per_mission: ["Spending limit per research", "Research stops requesting data at this limit and keeps what it found."],
  max_company_search_results: ["Companies reviewed", "How many matching companies are scored per research."],
  max_company_enrichments: ["Companies researched in depth", "Detailed data (growth, hiring, funding) is collected for the best matches."],
  max_buyer_searches: ["Companies searched for decision-makers", "Searched in ranked order until enough contacts are found."],
};

export default function SettingsPage() {
  const q = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  if (q.isLoading) return <Skeleton className="h-64" />;
  if (q.error || !q.data) return <Notice tone="bad" title="Can't reach the server">{(q.error as Error | null)?.message}</Notice>;
  const s = q.data;
  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" description="Connections and limits for this workspace." />
      <div className="space-y-6">
        <Card>
          <CardHeader title="Connections" description="Keys are stored on the server and are never shown in the app or included in reports." />
          <ul className="divide-y divide-line">
            <li className="flex items-center justify-between gap-4 px-5 py-4"><div><div className="text-sm font-medium">Company and people data</div><div className="text-[13px] text-muted">Crustdata. Required for new research (demo mode works without it).</div></div>
              <Pill tone={s.crustdata_key_set ? "ok" : "bad"}>{s.crustdata_key_set ? "Connected" : "Not connected"}</Pill></li>
            <li className="flex items-center justify-between gap-4 px-5 py-4"><div><div className="text-sm font-medium">AI writing assistant</div><div className="text-[13px] text-muted">Optional. Reads free-text briefs and polishes draft messages. Never produces numbers or facts.</div></div>
              <Pill tone={s.llm_key_set ? "ok" : "neutral"}>{s.llm_key_set ? "Connected" : "Off"}</Pill></li>
          </ul>
        </Card>
        <Card>
          <CardHeader title="Limits" description={`A typical research uses about ${Math.round(s.estimate.typical)} credits.`} />
          <dl className="divide-y divide-line">{Object.entries(s.caps).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-4 px-5 py-4"><div><dt className="text-sm font-medium">{LIMITS[k]?.[0] ?? k}</dt><dd className="text-[13px] text-muted">{LIMITS[k]?.[1]}</dd></div><div className="tabular text-sm font-semibold">{v.toLocaleString()}</div></div>))}</dl>
        </Card>
      </div>
    </div>
  );
}
