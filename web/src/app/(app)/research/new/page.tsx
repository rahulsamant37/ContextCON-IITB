"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState, useSyncExternalStore } from "react";
import { Button, Card, CardHeader, Field, Notice, PageHeader, Pill, Segmented, Skeleton, TagInput, inputBase, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Preview } from "@/lib/types";

type Size = "any" | "1-50" | "50-200" | "200-1000" | "1000+" | "custom";
interface Form { productName: string; description: string; country: string; industry: string; size: Size; min: string; max: string; acv: string; currency: string; roles: string[] }
const EMPTY: Form = { productName: "", description: "", country: "", industry: "", size: "any", min: "", max: "", acv: "", currency: "USD", roles: [] };
const EXAMPLES: Record<string, { label: string; form: Form }> = {
  germany: { label: "Fleet software · Germany logistics", form: { productName: "", description: "AI-driven fleet-maintenance software", country: "Germany", industry: "Logistics", size: "custom", min: "100", max: "1000", acv: "9000", currency: "EUR", roles: ["Head of Fleet", "VP Operations", "CTO"] } },
  uk: { label: "Compliance software · UK fintech", form: { productName: "", description: "cybersecurity compliance software", country: "United Kingdom", industry: "FinTech", size: "50-200", min: "", max: "", acv: "12000", currency: "GBP", roles: ["CISO", "Head of Compliance", "CTO"] } },
  india: { label: "Scheduling software · India healthcare", form: { productName: "", description: "patient-scheduling software", country: "India", industry: "Healthcare", size: "50-200", min: "", max: "", acv: "400000", currency: "INR", roles: ["CEO", "COO"] } },
};
const SIZES: { id: Size; label: string }[] = [{ id: "any", label: "Any size" }, { id: "1-50", label: "1–50" }, { id: "50-200", label: "50–200" }, { id: "200-1000", label: "200–1,000" }, { id: "1000+", label: "1,000+" }, { id: "custom", label: "Custom" }];

function sizeRange(f: Form): [number | null, number | null] {
  if (f.size === "custom") return [f.min ? Number(f.min) : null, f.max ? Number(f.max) : null];
  if (f.size === "any") return [null, null];
  if (f.size === "1000+") return [1000, null];
  const [a, b] = f.size.split("-").map(Number);
  return [a, b];
}
function sizeText(lo: number | null, hi: number | null) {
  if (lo != null && hi != null) return `${lo.toLocaleString()}–${hi.toLocaleString()} employees`;
  if (lo != null) return `more than ${lo.toLocaleString()} employees`;
  if (hi != null) return `fewer than ${hi.toLocaleString()} employees`;
  return "any size";
}

function NewResearchInner() {
  const router = useRouter();
  const params = useSearchParams();
  const ex = params.get("example");
  const [form, setForm] = useState<Form>(() => (ex && EXAMPLES[ex] ? EXAMPLES[ex].form : EMPTY));
  const [mode, setMode] = useState<"guided" | "text">("guided");
  const [text, setText] = useState("");
  const [demo, setDemo] = useState(ex === "germany");
  const [aiWording, setAiWording] = useState(true);
  const [simulate, setSimulate] = useState(false);
  const [touched, setTouched] = useState(false);
  const options = useQuery({ queryKey: ["options"], queryFn: api.options });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const set = (p: Partial<Form>) => setForm((f) => ({ ...f, ...p }));

  const [lo, hi] = sizeRange(form);
  const errors = useMemo(() => {
    const e: Partial<Record<keyof Form, string>> = {};
    if (form.description.trim().length < 3) e.description = "Describe your product in a few words.";
    if (!form.country) e.country = "Choose a country.";
    if (form.industry.trim().length < 2) e.industry = "Choose or type an industry.";
    if (lo != null && hi != null && lo > hi) e.max = "Maximum must be larger than minimum.";
    if (form.acv && !(Number(form.acv) > 0)) e.acv = "Enter a positive number, or leave it blank.";
    return e;
  }, [form, lo, hi]);
  const valid = Object.keys(errors).length === 0;

  const prompt = `We sell ${form.description.trim()} to ${form.industry.trim()} companies. Evaluate entry into ${form.country}, ${sizeText(lo, hi)}`
    + (form.acv ? `, ${form.currency} ${Number(form.acv)} annual contract value` : "") + (form.roles.length ? `, buyers: ${form.roles.join(" / ")}` : "") + ".";
  const overrides: Record<string, unknown> = {
    product_description: form.description.trim(), target_country: form.country, target_industry: form.industry.trim(),
    employee_min: lo, employee_max: hi, ...(form.acv ? { annual_contract_value: Number(form.acv), currency: form.currency } : {}),
    ...(form.roles.length ? { target_buyer_roles: form.roles } : {}), ...(form.productName.trim() ? { product_name: form.productName.trim() } : {}),
  };
  const runOpts = { replay: demo, simulate_failure: simulate, use_llm: demo ? false : aiWording && !!settings.data?.llm_key_set };
  const run = useMutation({
    mutationFn: () => (mode === "guided" ? api.create(prompt, runOpts, overrides) : api.create(text, runOpts)),
    onSuccess: (r) => router.push(`/research/${r.mission_id}/run`),
  });
  const preview = useMutation<Preview>({ mutationFn: () => api.preview(text, runOpts.use_llm) });
  const noKey = settings.data && !settings.data.crustdata_key_set && !demo;
  const canRun = mode === "guided" ? valid : text.trim().length >= 10;
  const est = settings.data?.estimate.typical;

  return (
    <>
      <PageHeader crumbs={[{ href: "/research", label: "Research" }, { label: "New research" }]} title="New research"
        description="Tell us what you sell and where. We find the companies, the people and the numbers, and show the source for each one." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Segmented label="Input mode" value={mode} onChange={setMode} options={[{ id: "guided", label: "Guided form" }, { id: "text", label: "Describe in your own words" }]} />
            {mode === "guided" && (
              <label className="flex items-center gap-2 text-[13px] text-muted">Start from an example
                <select aria-label="Example" className={`${inputBase} h-8 w-auto`} value="" onChange={(e) => { const k = e.target.value; if (EXAMPLES[k]) { setForm(EXAMPLES[k].form); setDemo(k === "germany"); } }}>
                  <option value="">Choose…</option>{Object.entries(EXAMPLES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>)}
          </div>

          {mode === "guided" ? (
            <form onSubmit={(e) => { e.preventDefault(); setTouched(true); if (valid) run.mutate(); }} className="space-y-5" noValidate>
              <Card>
                <CardHeader title="What are you selling?" />
                <div className="grid gap-4 p-5 sm:grid-cols-2">
                  <Field label="Describe your product" htmlFor="desc" error={touched ? errors.description : undefined} hint="A few words, e.g. “cybersecurity compliance software”.">
                    <input id="desc" data-testid="f-description" className={inputCls} value={form.description} onChange={(e) => set({ description: e.target.value })} placeholder="e.g. fleet-maintenance software" /></Field>
                  <Field label="Product name" htmlFor="pname" optional><input id="pname" className={inputCls} value={form.productName} onChange={(e) => set({ productName: e.target.value })} placeholder="e.g. FleetPilot" /></Field>
                </div>
              </Card>
              <Card>
                <CardHeader title="Which market?" description="We search companies headquartered in this country and sector." />
                <div className="grid gap-4 p-5 sm:grid-cols-2">
                  <Field label="Country" htmlFor="country" error={touched ? errors.country : undefined}>
                    <select id="country" data-testid="f-country" className={inputCls} value={form.country} onChange={(e) => set({ country: e.target.value })}>
                      <option value="">Select a country</option>{options.data?.countries.map((c) => <option key={c}>{c}</option>)}</select></Field>
                  <Field label="Industry" htmlFor="industry" error={touched ? errors.industry : undefined} hint="Pick a suggestion or type your own.">
                    <input id="industry" data-testid="f-industry" list="sectors" className={inputCls} value={form.industry} onChange={(e) => set({ industry: e.target.value })} placeholder="e.g. Logistics" />
                    <datalist id="sectors">{options.data?.sectors.map((s) => <option key={s} value={s} />)}</datalist></Field>
                  <div className="sm:col-span-2">
                    <Field label="Company size (employees)" error={touched ? errors.max : undefined}>
                      <Segmented label="Company size" value={form.size} onChange={(v) => set({ size: v })} options={SIZES} />
                      {form.size === "custom" && (
                        <div className="mt-3 flex items-center gap-2"><input aria-label="Minimum employees" inputMode="numeric" className={`${inputBase} w-32`} placeholder="Min" value={form.min} onChange={(e) => set({ min: e.target.value.replace(/\D/g, "") })} />
                          <span className="text-muted">to</span><input aria-label="Maximum employees" inputMode="numeric" className={`${inputBase} w-32`} placeholder="Max" value={form.max} onChange={(e) => set({ max: e.target.value.replace(/\D/g, "") })} /></div>)}
                    </Field>
                  </div>
                </div>
              </Card>
              <Card>
                <CardHeader title="Deal size and buyers" />
                <div className="grid gap-4 p-5">
                  <Field label="Typical annual contract value" optional error={touched ? errors.acv : undefined} hint="Used to estimate what the market is worth. Leave blank and we won't show any money figures.">
                    <div className="flex max-w-sm gap-2">
                      <select aria-label="Currency" className={`${inputBase} w-24`} value={form.currency} onChange={(e) => set({ currency: e.target.value })}>{(options.data?.currencies ?? ["USD"]).map((c) => <option key={c}>{c}</option>)}</select>
                      <input aria-label="Annual contract value" data-testid="f-acv" inputMode="decimal" className={inputCls} placeholder="e.g. 12000" value={form.acv} onChange={(e) => set({ acv: e.target.value.replace(/[^\d.]/g, "") })} /></div></Field>
                  <Field label="Who buys it?" optional hint="Job titles of the people who usually decide. We only list people whose title matches.">
                    <TagInput id="roles" values={form.roles} onChange={(v) => set({ roles: v })} suggestions={options.data?.roles ?? []} placeholder="Type a job title and press Enter" /></Field>
                </div>
              </Card>
              <button type="submit" hidden />
            </form>
          ) : (
            <Card>
              <CardHeader title="Describe the market you are considering" description="Include what you sell, the country, the sector, company size, deal size and who buys." />
              <div className="space-y-3 p-5">
                <textarea data-testid="prompt-input" aria-label="Research request" rows={6} value={text} onChange={(e) => { setText(e.target.value); preview.reset(); }} className={`${inputCls} h-auto py-2`}
                  placeholder="We sell compliance software to fintech companies. Evaluate entry into the UK, 50–500 employees, £12,000 a year, buyers: CISO / Head of Compliance." />
                <Button variant="secondary" size="sm" disabled={text.trim().length < 10 || preview.isPending} onClick={() => preview.mutate()} data-testid="review-btn">
                  {preview.isPending && <Loader2 size={14} className="animate-spin" />}Check what we understood</Button>
                {preview.data && (
                  <div className="rounded-md border border-line" data-testid="brief-card">
                    <dl className="grid gap-x-6 gap-y-2 p-4 text-sm sm:grid-cols-2">{[
                      ["Country", preview.data.brief.target_country], ["Industry", preview.data.brief.target_industry],
                      ["Company size", sizeText(preview.data.brief.employee_min, preview.data.brief.employee_max)],
                      ["Contract value", preview.data.brief.annual_contract_value != null ? `${preview.data.brief.currency ?? ""} ${preview.data.brief.annual_contract_value.toLocaleString()}` : "Not given"],
                      ["Buyers", preview.data.brief.target_buyer_roles.join(", ")], ["Product", preview.data.brief.product_description]].map(([k, v]) => (
                        <div key={k}><dt className="text-xs text-muted">{k}</dt><dd className={v === "unknown" ? "text-warn" : "text-ink"}>{v === "unknown" ? "Not recognised" : v}</dd></div>))}</dl>
                    {!preview.data.ready && <div className="border-t border-line p-3"><Notice tone="warn" title="We couldn't recognise the country or industry">Name both clearly, or switch to the guided form.</Notice></div>}
                  </div>)}
              </div>
            </Card>)}

          <details className="group rounded-lg border border-line bg-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-3.5 text-sm font-medium">Options<ChevronDown size={16} className="text-muted transition group-open:rotate-180" /></summary>
            <div className="space-y-3 border-t border-line px-5 py-4 text-sm">
              <label className="flex items-start gap-3"><input type="checkbox" data-testid="option-replay" className="mt-0.5 h-4 w-4 accent-[var(--accent)]" checked={demo} onChange={(e) => setDemo(e.target.checked)} />
                <span><span className="font-medium">Demo mode</span><span className="block text-[13px] text-muted">Uses saved data from an earlier run, so it is free and instant. Only works for requests that were run before (try the Germany example).</span></span></label>
              <label className="flex items-start gap-3"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={aiWording && !demo} disabled={demo || !settings.data?.llm_key_set} onChange={(e) => setAiWording(e.target.checked)} />
                <span><span className="font-medium">Polish wording with AI</span><span className="block text-[13px] text-muted">{settings.data?.llm_key_set ? "Improves draft messages. AI never produces numbers or facts." : "Not configured on the server; templates are used."}</span></span></label>
              <label className="flex items-start gap-3"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={simulate} onChange={(e) => setSimulate(e.target.checked)} />
                <span><span className="font-medium">Simulate a temporary outage</span><span className="block text-[13px] text-muted">Shows how the research recovers from a failed request.</span></span></label>
            </div>
          </details>
        </div>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <Card>
            <CardHeader title="Your brief" />
            <div className="space-y-4 p-5 text-sm">
              {mode === "guided" ? (
                <p className="leading-relaxed text-ink-2" data-testid="brief-summary">
                  Find <b className="text-ink">{form.industry || "…"}</b> companies in <b className="text-ink">{form.country || "…"}</b> with <b className="text-ink">{sizeText(lo, hi)}</b> that could buy <b className="text-ink">{form.description || "your product"}</b>
                  {form.acv ? <> at about <b className="text-ink">{form.currency} {Number(form.acv).toLocaleString()}</b> a year</> : null}.
                  {form.roles.length > 0 && <> Look for <b className="text-ink">{form.roles.join(", ")}</b>.</>}
                </p>) : <p className="text-ink-2">We will read your description and run the research. Use “Check what we understood” first if you want to confirm.</p>}
              <ul className="space-y-1.5 text-[13px] text-ink-2">{["Ranked list of target companies", "Decision-makers, confirmed by employer", "Competitors in your space", "Market value estimate", "Report, spreadsheets and a sales pipeline"].map((x) => (
                <li key={x} className="flex items-start gap-2"><Check size={14} className="mt-0.5 shrink-0 text-accent" />{x}</li>))}</ul>
              <div className="flex items-center justify-between border-t border-line pt-3 text-[13px]"><span className="text-muted">Estimated time</span><span>{demo ? "A few seconds" : "About 1 minute"}</span></div>
              <div className="-mt-2 flex items-center justify-between text-[13px]"><span className="text-muted">Data cost</span>{demo ? <Pill tone="ok">Free (demo)</Pill> : <span>{est ? `About ${Math.round(est)} credits` : "…"}</span>}</div>
              {noKey && <Notice tone="bad" title="Data connection not set up">Add the Crustdata key on the server, or turn on Demo mode.</Notice>}
              {run.error && <Notice tone="bad" title="Couldn't start the research">{(run.error as Error).message}</Notice>}
              <Button data-testid="run-btn" className="w-full" size="lg" disabled={run.isPending || !!noKey || (mode === "text" && !canRun)}
                onClick={() => { setTouched(true); if (canRun) run.mutate(); }}>
                {run.isPending && <Loader2 size={16} className="animate-spin" />}Start research</Button>
              {mode === "guided" && touched && !valid && <p className="text-center text-xs text-bad">Please complete the highlighted fields.</p>}
              <p className="text-center text-xs text-muted">No messages are ever sent on your behalf.</p>
            </div>
          </Card>
        </aside>
      </div>
    </>
  );
}

const noop = () => () => {};

export default function NewResearch() {
  // Purely interactive page whose text depends on server settings: render after hydration to avoid SSR mismatches.
  const hydrated = useSyncExternalStore(noop, () => true, () => false);
  if (!hydrated) return <div className="space-y-4"><Skeleton className="h-8 w-56" /><Skeleton className="h-64" /></div>;
  return <Suspense fallback={null}><NewResearchInner /></Suspense>;
}
