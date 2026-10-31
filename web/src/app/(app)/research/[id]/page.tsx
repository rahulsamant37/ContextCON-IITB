"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Companies } from "@/components/results/companies";
import { CompanyPanel } from "@/components/results/company-panel";
import { Overview } from "@/components/results/overview";
import { Brief, Competitors, DecisionMakers, Downloads, Sources } from "@/components/results/tabs";
import { Button, LinkButton, Notice, PageHeader, Pill, Skeleton, Tabs } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { ago, STATE } from "@/lib/format";

type Tab = "overview" | "companies" | "people" | "competitors" | "sources" | "brief" | "downloads";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [company, setCompany] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["mission", id], queryFn: () => api.mission(id), retry: false });
  const rerun = useMutation({
    mutationFn: () => api.create(q.data!.brief!.raw_prompt, { replay: false, simulate_failure: false, use_llm: true }),
    onSuccess: (r) => router.push(`/research/${r.mission_id}/run`),
  });
  useEffect(() => { if (q.error instanceof ApiError && q.error.status === 409) router.replace(`/research/${id}/run`); }, [q.error, id, router]);

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-80" /><Skeleton className="h-20" /><Skeleton className="h-28" /><Skeleton className="h-72" /></div>;
  if (q.error || !q.data) return <Notice tone="bad" title="Couldn't load this research" action={<LinkButton href="/research" size="sm" variant="secondary">Back to research</LinkButton>}>{(q.error as Error | null)?.message}</Notice>;
  const m = q.data; const b = m.brief;

  if (!b || m.state === "failed") return (
    <div className="mx-auto max-w-2xl">
      <PageHeader crumbs={[{ href: "/research", label: "Research" }, { label: "Could not complete" }]} title="This research couldn't be completed" description="We stop rather than fill gaps with guesses. Here's what happened:" />
      <ul className="mb-6 list-disc space-y-1.5 pl-5 text-sm text-ink-2" data-testid="failure-reasons">{m.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
      <LinkButton href="/research/new">Try again with a clearer brief</LinkButton>
    </div>);

  const people = Object.values(m.people).reduce((n, v) => n + v.length, 0);
  const st = STATE[m.state];
  return (
    <>
      <PageHeader crumbs={[{ href: "/research", label: "Research" }, { label: `${b.target_industry} in ${b.target_country}` }]}
        title={<span data-testid="mission-title">{b.target_industry} in {b.target_country}</span>}
        meta={<Pill tone={st.tone}>{st.label}</Pill>}
        description={`${b.product_description} · ${b.employee_min != null || b.employee_max != null ? `${b.employee_min ?? "any"}–${b.employee_max ?? "any"} employees` : "any company size"} · ${ago(m.finished_at ?? m.started_at)}`}
        actions={<>
          <Button variant="ghost" size="sm" disabled={rerun.isPending} onClick={() => rerun.mutate()} title="Run again with fresh data"><RefreshCw size={14} />Refresh data</Button>
          <LinkButton href={`/research/${id}/pipeline`} variant="secondary" data-testid="open-crm">Open pipeline</LinkButton>
          {m.artifacts.includes("Market_Entry_Report.pdf") && <a href={api.artifactUrl(id, "Market_Entry_Report.pdf")} download className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-ink hover:opacity-90"><Download size={15} />Download report</a>}
        </>} />
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "overview", label: "Overview" }, { id: "companies", label: "Companies", count: m.accounts.length }, { id: "people", label: "Decision-makers", count: people },
        { id: "competitors", label: "Competitors", count: m.competitors.length }, { id: "sources", label: "Sources", count: m.verification?.checked },
        { id: "brief", label: "Brief" }, { id: "downloads", label: "Downloads" }]} />
      <div className="pt-6">
        {tab === "overview" && <Overview m={m} onOpenCompany={setCompany} onShowAll={() => setTab("companies")} />}
        {tab === "companies" && <Companies accounts={m.accounts} onOpen={setCompany} />}
        {tab === "people" && <DecisionMakers m={m} onOpen={setCompany} />}
        {tab === "competitors" && <Competitors m={m} />}
        {tab === "sources" && <Sources missionId={id} total={m.verification?.checked ?? 0} fraction={m.verified_claim_fraction} />}
        {tab === "brief" && <Brief m={m} />}
        {tab === "downloads" && <Downloads m={m} />}
      </div>
      <CompanyPanel missionId={id} companyId={company} onClose={() => setCompany(null)} />
    </>
  );
}
