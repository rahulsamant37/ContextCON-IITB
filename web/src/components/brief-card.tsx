"use client";
import { Badge, Callout, Card, CardHeader, type Tone } from "./ui";
import type { Brief, Source } from "@/lib/types";

const srcTone: Record<Source, Tone> = { user: "good", inferred: "brand", defaulted: "warn" };
const srcHint: Record<Source, string> = { user: "stated in your request", inferred: "inferred by the language model from your text", defaulted: "not stated: a visible default or unknown" };

export type Overrides = Partial<Pick<Brief, "target_country" | "target_industry" | "employee_min" | "employee_max" | "annual_contract_value" | "currency" | "target_buyer_roles">>;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-muted">{label}<div className="mt-1">{children}</div></label>;
}
const inputCls = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-brand";

export function BriefCard({ brief, values, onChange, estimate }: { brief: Brief; values: Overrides; onChange: (v: Overrides) => void; estimate?: { typical: number; cap: number } }) {
  const v = { ...brief, ...values };
  const set = (patch: Overrides) => onChange({ ...values, ...patch });
  const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));
  return (
    <Card data-testid="brief-card">
      <CardHeader title="Here is what I understood" sub="Edit anything that looks wrong, or just run it. Unstated values stay unknown; nothing is invented."
        right={estimate && <Badge tone="neutral" title={`Hard cap per mission: ${estimate.cap} credits`}>≈ {estimate.typical} credits (cap {estimate.cap})</Badge>} />
      <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Target country"><input className={inputCls} value={v.target_country} onChange={(e) => set({ target_country: e.target.value })} /></Field>
        <Field label="Target sector"><input className={inputCls} value={v.target_industry} onChange={(e) => set({ target_industry: e.target.value })} /></Field>
        <Field label="Employees min"><input className={inputCls} inputMode="numeric" value={v.employee_min ?? ""} placeholder="any" onChange={(e) => set({ employee_min: numOrNull(e.target.value) })} /></Field>
        <Field label="Employees max"><input className={inputCls} inputMode="numeric" value={v.employee_max ?? ""} placeholder="any" onChange={(e) => set({ employee_max: numOrNull(e.target.value) })} /></Field>
        <Field label="Annual contract value"><input className={inputCls} inputMode="decimal" value={v.annual_contract_value ?? ""} placeholder="not supplied: no money figures" onChange={(e) => set({ annual_contract_value: numOrNull(e.target.value) })} /></Field>
        <Field label="Currency"><input className={inputCls} value={v.currency ?? ""} placeholder="e.g. GBP" onChange={(e) => set({ currency: e.target.value.toUpperCase() || null })} /></Field>
        <div className="sm:col-span-2"><Field label="Buyer roles (comma separated)"><input className={inputCls} value={v.target_buyer_roles.join(", ")} onChange={(e) => set({ target_buyer_roles: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} /></Field></div>
      </div>
      {brief.unsupported_constraints.length > 0 && <div className="px-5 pb-4"><Callout tone="warn" title="Needs attention">{brief.unsupported_constraints.join("; ")}</Callout></div>}
      <details className="border-t border-border px-5 py-3">
        <summary className="cursor-pointer text-sm font-medium">Assumption ledger ({brief.assumptions.length})</summary>
        <table className="mt-3 w-full text-left text-sm">
          <thead className="text-xs text-muted"><tr><th className="py-1 pr-3">Field</th><th className="pr-3">Value</th><th className="pr-3">Source</th><th>Note</th></tr></thead>
          <tbody>{brief.assumptions.map((a, i) => (
            <tr key={i} className="border-t border-border align-top">
              <td className="py-1.5 pr-3 font-medium">{a.field}</td>
              <td className="pr-3 font-mono text-xs">{a.value == null ? <span className="text-warn">unknown</span> : Array.isArray(a.value) ? a.value.join(", ") : String(a.value)}</td>
              <td className="pr-3"><Badge tone={srcTone[a.source]} title={srcHint[a.source]}>{a.source}</Badge></td>
              <td className="text-xs text-muted">{a.note}</td>
            </tr>))}</tbody>
        </table>
      </details>
    </Card>
  );
}
