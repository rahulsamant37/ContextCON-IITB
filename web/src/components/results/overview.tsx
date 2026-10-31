"use client";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { Badge, Callout, Card, CardHeader, Stat } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import type { Mission, Wave } from "@/lib/types";

const WAVE_COLOR: Record<string, string> = { "Wave 1": "#14804a", "Wave 2": "#3b5bdb", "Research Needed": "#d98a00" };

export function Overview({ m }: { m: Mission }) {
  const b = m.brief!;
  const people = Object.values(m.people).reduce((n, v) => n + v.length, 0);
  const verdictTone = m.recommendation.verdict.startsWith("Proceed:") ? "good" : m.recommendation.verdict.startsWith("Proceed") ? "warn" : "bad";
  const waveData = (Object.keys(m.waves) as Wave[]).map((k) => ({ name: k, value: m.waves[k] }));
  const scatter = m.accounts.filter((a) => a.employee_count != null && a.headcount_growth_6m != null).map((a) => ({ x: a.employee_count!, y: a.headcount_growth_6m!, name: a.name, wave: a.wave ?? "Research Needed" }));
  const wave1 = m.accounts.filter((a) => a.wave === "Wave 1").map((a) => a.name);
  const supported = m.verified_claim_fraction;

  return (
    <div className="space-y-5" data-testid="overview">
      <Callout tone={verdictTone} title={m.recommendation.verdict}>{m.recommendation.text}</Callout>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Stat label="Indexed companies" value={num(m.universe.total_count)} hint="observed, coverage-limited" tone={m.universe.total_count == null ? "warn" : undefined} />
        <Stat label="Shortlisted" value={m.accounts.length} hint={`${m.universe.fetched} candidates scored`} />
        <Stat label="Wave 1" value={m.waves["Wave 1"]} hint="fit + verified buyer" tone="good" />
        <Stat label="Verified buyers" value={people} hint="employer matched by ID" />
        <Stat label="Claims verified" value={supported == null ? "unknown" : `${Math.round(supported * 100)}%`} hint={`${m.verification?.checked ?? 0} checked`} tone={supported != null && supported < 0.95 ? "warn" : "good"} />
        <Stat label="Credits used" value={m.credit_used == null ? "unknown" : m.credit_used.toFixed(1)} />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="Bottom-up market sizing" sub="Observed indexed count × your assumed contract value" right={<Badge tone="neutral">illustrative, not TAM</Badge>} />
          <div className="space-y-3 p-5">
            {m.sizing.pool != null && m.sizing.acv != null ? (
              <div className="flex flex-wrap items-center gap-3 text-lg font-semibold tabular-nums" data-testid="sizing-formula">
                <span className="rounded-lg bg-surface-2 px-3 py-2">{num(m.sizing.observed_count)} <span className="text-sm font-normal text-muted">indexed companies</span></span>×
                <span className="rounded-lg bg-surface-2 px-3 py-2">{money(m.sizing.acv, m.sizing.currency)} <span className="text-sm font-normal text-muted">ACV (yours)</span></span>=
                <span className="rounded-lg bg-brand-soft px-3 py-2 text-brand">{money(m.sizing.pool, m.sizing.currency)}</span>
              </div>) : <p className="text-sm" data-testid="sizing-none">{m.sizing.formula_text}</p>}
            {m.sizing.pipeline_pool != null && <p className="text-sm text-muted">Identified pipeline: {m.accounts.filter((a) => a.wave).length} shortlisted resolved accounts × ACV = <b className="text-text">{money(m.sizing.pipeline_pool, m.sizing.currency)}</b> (not a forecast).</p>}
            <details className="text-xs text-muted"><summary className="cursor-pointer font-medium">Caveats and exact filters</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">{m.sizing.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
              <p className="mt-2">Sector basis: {m.sector_basis}</p>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-surface-2 p-3 text-[11px]">{JSON.stringify(m.universe.filters_applied, null, 1)}</pre>
            </details>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Launch segments" />
          <div className="h-48 px-2 py-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={waveData} margin={{ left: 0, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted)" }} /><YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted)" }} width={28} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} isAnimationActive={false}>{waveData.map((d) => <Cell key={d.name} fill={WAVE_COLOR[d.name]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {scatter.length > 0 && (
        <Card>
          <CardHeader title="Fit landscape" sub="Headcount vs 6-month growth. Growth is an indicator, not purchase intent." />
          <div className="h-72 px-2 py-3" aria-label="Scatter chart of headcount against growth">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ left: 0, right: 16, top: 8, bottom: 22 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis type="number" dataKey="x" name="Headcount" tick={{ fontSize: 11, fill: "var(--muted)" }} label={{ value: "Headcount (people)", position: "insideBottom", offset: -4, fontSize: 11, fill: "var(--muted)" }} /><YAxis type="number" dataKey="y" name="Growth %" tick={{ fontSize: 11, fill: "var(--muted)" }} width={44} label={{ value: "6-month growth %", angle: -90, position: "insideLeft", fontSize: 11, fill: "var(--muted)" }} /><ZAxis range={[60, 60]} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ payload }) => payload?.[0] ? (
                  <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow"><b>{payload[0].payload.name}</b><br />{payload[0].payload.x} people · {pct(payload[0].payload.y)}<br />{payload[0].payload.wave}</div>) : null} />
                <Scatter data={scatter} isAnimationActive={false}>{scatter.map((d, i) => <Cell key={i} fill={WAVE_COLOR[d.wave]} />)}</Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Card>)}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHeader title="Prioritised launch plan" />
          <ol className="list-decimal space-y-2 px-9 py-4 text-sm">
            <li><b>Wave 1 ({m.waves["Wave 1"]}):</b> {wave1.length ? wave1.join(", ") : "none qualified yet"}. Review the drafts in the CRM, personalise, then a human sends.</li>
            <li><b>Wave 2 ({m.waves["Wave 2"]}):</b> verify buyers, then promote to Wave 1.</li>
            <li><b>Research Needed ({m.waves["Research Needed"]}):</b> close the data gaps listed in each research task.</li>
            <li>Confirm the ACV{b.annual_contract_value == null ? " (none was supplied)" : ""} with the client before sharing sizing externally.</li>
          </ol></Card>
        <Card><CardHeader title="Key risks and limitations" />
          <ul className="list-disc space-y-1.5 px-9 py-4 text-sm text-muted">{m.risks.map((r) => <li key={r}>{r}</li>)}</ul></Card>
      </div>

      {m.warnings.length > 0 && (
        <details className="rounded-xl border border-border bg-surface px-5 py-3 text-sm">
          <summary className="cursor-pointer font-medium">Notes and warnings ({m.warnings.length}): honest gaps, never hidden</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">{m.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </details>)}
    </div>
  );
}
