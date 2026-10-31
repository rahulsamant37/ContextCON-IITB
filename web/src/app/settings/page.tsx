"use client";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { Callout, Card, CardHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

const LABEL: Record<string, string> = { max_credits_per_mission: "Credit cap per mission", max_company_enrichments: "Accounts enriched", max_company_search_results: "Candidates fetched", max_buyer_searches: "Accounts searched for buyers" };

const Row = ({ ok, label, hint }: { ok: boolean; label: string; hint: string }) => (
  <li className="flex items-center gap-3 px-5 py-3 text-sm">{ok ? <CheckCircle2 className="text-good" size={18} /> : <XCircle className="text-bad" size={18} />}<div><div className="font-medium">{label}</div><div className="text-xs text-muted">{hint}</div></div></li>
);

export default function SettingsPage() {
  const q = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  if (q.isLoading) return <Skeleton className="h-64" />;
  if (q.error || !q.data) return <Callout tone="bad" title="Cannot reach the server">{(q.error as Error | null)?.message}</Callout>;
  const s = q.data;
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <Card><CardHeader title="Connections" sub="Keys are read from the server environment. They are never sent to this page or stored in results." />
        <ul className="divide-y divide-border">
          <Row ok={s.crustdata_key_set} label="Crustdata API" hint={s.crustdata_key_set ? "Key configured on the server." : "Set CRUSTDATA_API_KEY on the server (or use offline replay)."} />
          <Row ok={s.llm_key_set} label={`Language model (${s.llm_model})`} hint={s.llm_key_set ? "Used only to parse your text and polish draft wording; numbers and facts never come from it." : "Optional. Without a key, rules and templates are used."} />
        </ul></Card>
      <Card><CardHeader title="Cost controls" sub={`A typical mission costs about ${s.estimate.typical} credits.`} />
        <dl className="divide-y divide-border">{Object.entries(s.caps).map(([k, v]) => <div key={k} className="flex justify-between px-5 py-2.5 text-sm"><dt className="text-muted">{LABEL[k] ?? k}</dt><dd className="font-medium tabular-nums">{v}</dd></div>)}</dl>
        <p className="px-5 pb-4 text-xs text-muted">Caps are set on the server and enforced before every call; a run stops spending when it reaches the cap and keeps partial results.</p></Card>
    </div>
  );
}
