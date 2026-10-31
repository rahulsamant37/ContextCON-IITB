"use client";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Card, CardHeader, Metric, Notice, Pill } from "@/components/ui";
import { money, num, PRIORITY, priority } from "@/lib/format";
import type { Mission } from "@/lib/types";

export function recommendation(m: Mission) {
  const w1 = m.waves["Wave 1"], w2 = m.waves["Wave 2"], total = m.universe.total_count;
  const b = m.brief!;
  const where = `${b.target_industry} companies in ${b.target_country}`;
  if (m.sector_basis.startsWith("unverified")) return { tone: "warn" as const, title: "Results need a closer look", text: `We couldn't match “${b.target_industry}” to a known industry category, so the companies below are ranked by relevance and their industry isn't confirmed. Try a more common industry name for a sharper list.` };
  if (!total) return { tone: "bad" as const, title: "Not enough data to recommend this market", text: `We couldn't find ${where} matching your filters. Try a broader size range or a different industry name.` };
  const base = `We found ${total.toLocaleString()} ${where} in your size range. ${w1} ${w1 === 1 ? "is" : "are"} ready to contact now and ${w2} more ${w2 === 1 ? "is" : "are"} a good fit but still need a confirmed decision-maker.`;
  if (w1 >= 3) return { tone: "ok" as const, title: `Worth pursuing: start with ${w1} companies`, text: base };
  if (w1 + w2 >= 5) return { tone: "info" as const, title: "Promising: confirm decision-makers first", text: base };
  return { tone: "warn" as const, title: "Hold off for now", text: base };
}

export function Overview({ m, onOpenCompany, onShowAll }: { m: Mission; onOpenCompany: (id: string) => void; onShowAll: () => void }) {
  const b = m.brief!;
  const rec = recommendation(m);
  const people = Object.values(m.people).reduce((n, v) => n + v.length, 0);
  const top = m.accounts.filter((a) => a.wave).slice(0, 6);
  const total = m.accounts.length || 1;
  const checked = m.verification?.checked ?? 0;
  const fraction = m.verified_claim_fraction;

  return (
    <div className="space-y-6" data-testid="overview">
      <Notice tone={rec.tone} title={<span className="text-[15px]" data-testid="recommendation">{rec.title}</span>}>
        {rec.text} <span className="text-muted">Company data shows fit, not intent to buy.</span>
      </Notice>

      <Card className="grid divide-y divide-line sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
        <Metric label="Companies found" value={num(m.universe.total_count)} help="Companies in Crustdata's database matching your country, industry and size. The real market may be larger." sub={`${m.accounts.length} shortlisted`} />
        <Metric label="Ready to contact" value={m.waves["Wave 1"]} help="Strong fit and a decision-maker whose employer we confirmed." sub={`${m.waves["Wave 2"]} more next in line`} />
        <Metric label="Decision-makers found" value={people} help="People in your buyer roles whose current employer matches the company." sub={b.target_buyer_roles.slice(0, 3).join(", ")} />
        <Metric label="Estimated market value" value={m.sizing.pool != null ? money(m.sizing.pool, m.sizing.currency, true) : "—"}
          help="Companies found × your annual contract value. A rough guide, not a revenue forecast."
          sub={m.sizing.pool != null ? `${num(m.sizing.observed_count)} × ${money(m.sizing.acv, m.sizing.currency)} per year` : b.annual_contract_value == null ? "Add a contract value to estimate" : "Not available"} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader title="Top companies to approach" description="Ranked by how well they match. Click a company for details and sources."
            action={<button onClick={onShowAll} className="flex items-center gap-1 text-[13px] font-medium text-accent hover:underline">View all {m.accounts.length}<ArrowRight size={14} /></button>} />
          <ul className="divide-y divide-line">{top.map((a) => {
            const p = priority(a.wave);
            return (
              <li key={a.company_id ?? a.name}>
                <button onClick={() => a.company_id && onOpenCompany(a.company_id)} className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-subtle" data-testid="top-company">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-subtle text-sm font-semibold text-ink-2">{a.name.charAt(0)}</div>
                  <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-ink">{a.name}</div><div className="truncate text-[13px] text-muted">{a.domain ?? "No website"} · {num(a.employee_count)} employees</div></div>
                  <Pill tone={p.tone}>{p.label}</Pill>
                  <span className="tabular w-10 text-right text-sm font-semibold">{a.fit_score ?? "—"}</span>
                </button>
              </li>);
          })}</ul>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Priority breakdown" />
            <div className="p-5">
              <div className="flex h-2.5 overflow-hidden rounded-full bg-subtle">
                {(["Wave 1", "Wave 2", "Research Needed"] as const).map((w) => <div key={w} className={{ "Wave 1": "bg-ok", "Wave 2": "bg-info", "Research Needed": "bg-warn" }[w]} style={{ width: `${(m.waves[w] / total) * 100}%` }} />)}
              </div>
              <ul className="mt-4 space-y-2.5 text-sm">{(["Wave 1", "Wave 2", "Research Needed"] as const).map((w) => (
                <li key={w} className="flex items-start justify-between gap-3"><div><Pill tone={PRIORITY[w].tone}>{PRIORITY[w].label}</Pill><p className="mt-1 text-[13px] text-muted">{PRIORITY[w].help}</p></div><span className="tabular font-semibold">{m.waves[w]}</span></li>))}</ul>
            </div>
          </Card>
          <Card>
            <CardHeader title="How reliable is this?" />
            <div className="space-y-3 p-5 text-[13px] text-ink-2">
              <p className="flex items-start gap-2"><ShieldCheck size={16} className="mt-0.5 shrink-0 text-ok" />
                <span><b className="text-ink">{fraction != null ? `${Math.round(fraction * 100)}%` : "—"}</b> of {checked.toLocaleString()} facts were confirmed against the original data.</span></p>
              <p>Missing information is shown as “Not available”, never guessed.</p>
              <p>No one has been contacted. Draft messages wait in your pipeline for review.</p>
            </div>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader title="Things to keep in mind" />
        <ul className="list-disc space-y-1.5 py-4 pl-10 pr-5 text-[13px] text-ink-2">{m.risks.map((r) => <li key={r}>{r}</li>)}</ul>
      </Card>
    </div>
  );
}
