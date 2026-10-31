"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { FileCheck2, Loader2, ScanSearch, Sparkles, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BriefCard, type Overrides } from "@/components/brief-card";
import { Button, Callout, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

const EXAMPLES = [
  { label: "UK fintech compliance", text: "We sell cybersecurity compliance software for financial technology companies. Evaluate entry into the UK fintech market. Focus on companies with 50–500 employees. Estimate the addressable company universe using a £12,000 annual contract value assumption; identify competitors and buyer roles; buyers: CISO / Head of Compliance / CTO." },
  { label: "Germany logistics", text: "We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, 100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO." },
  { label: "India healthcare", text: "We sell patient-scheduling software to healthcare providers. Evaluate entry into India, 50–300 employees, ₹400,000 annual contract value, buyers: CEO / COO." },
];

export default function NewMission() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [overrides, setOverrides] = useState<Overrides>({});
  const [opts, setOpts] = useState({ replay: false, simulate_failure: false, use_llm: true });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const preview = useMutation({ mutationFn: () => api.preview(prompt, opts.use_llm), onSuccess: () => setOverrides({}) });
  const run = useMutation({
    mutationFn: () => api.create(prompt, opts, Object.keys(overrides).length ? (overrides as Record<string, unknown>) : undefined),
    onSuccess: (r) => router.push(`/missions/${r.mission_id}/run`),
  });
  const tooShort = prompt.trim().length < 10;
  const noKey = settings.data && !settings.data.crustdata_key_set && !opts.replay && !settings.data.replay_default;
  const err = (preview.error ?? run.error) as ApiError | null;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="py-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Market-entry research you can audit</h1>
        <p className="mx-auto mt-3 max-w-2xl text-muted">Describe your product, target market and customer. Get a verified account list, buyer map, competitor scan, market sizing and a ready-to-work CRM, with every number linked to its source.</p>
      </div>

      <Card className="p-5">
        <label htmlFor="prompt" className="text-sm font-semibold">What do you want to evaluate?</label>
        <textarea id="prompt" data-testid="prompt-input" value={prompt} onChange={(e) => { setPrompt(e.target.value); preview.reset(); }} rows={5} maxLength={4000}
          placeholder="We sell … to … companies. Evaluate entry into … with … employees, ACV …, buyers: …"
          className="mt-2 w-full resize-y rounded-lg border border-border bg-surface px-3 py-2.5 text-sm focus:border-brand" />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">Try an example:</span>
          {EXAMPLES.map((e) => (
            <button key={e.label} onClick={() => { setPrompt(e.text); preview.reset(); }} className="rounded-full border border-border px-3 py-1 text-xs hover:bg-surface-2">{e.label}</button>
          ))}
        </div>

        <details className="mt-4 rounded-lg border border-border px-4 py-2.5">
          <summary className="cursor-pointer text-sm font-medium">Run options</summary>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
            <label className="flex items-start gap-2"><input type="checkbox" data-testid="option-replay" className="mt-1" checked={opts.replay} onChange={(e) => setOpts({ ...opts, replay: e.target.checked })} /><span><b>Offline replay</b><br /><span className="text-xs text-muted">Use recorded responses: 0 credits (only for requests recorded before)</span></span></label>
            <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={opts.simulate_failure} onChange={(e) => setOpts({ ...opts, simulate_failure: e.target.checked })} /><span><b>Simulate one API failure</b><br /><span className="text-xs text-muted">Shows retry and warning handling</span></span></label>
            <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={opts.use_llm} disabled={!settings.data?.llm_key_set} onChange={(e) => setOpts({ ...opts, use_llm: e.target.checked })} /><span><b>Use AI for wording</b><br /><span className="text-xs text-muted">{settings.data?.llm_key_set ? "Parses text and polishes drafts; never touches numbers" : "No LLM key set: rules and templates are used"}</span></span></label>
          </div>
        </details>

        {noKey && <div className="mt-4"><Callout tone="bad" title="Crustdata API key not configured">Set CRUSTDATA_API_KEY on the server, or tick “Offline replay”.</Callout></div>}
        {err && <div className="mt-4"><Callout tone="bad" title="Something went wrong">{err.message}</Callout></div>}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button data-testid="run-btn" size="lg" disabled={tooShort || run.isPending || !!noKey} onClick={() => run.mutate()}>
            {run.isPending ? <Loader2 className="animate-spin" size={18} /> : <Sparkles size={18} />} Run mission
          </Button>
          <Button data-testid="review-btn" variant="secondary" disabled={tooShort || preview.isPending} onClick={() => preview.mutate()}>
            {preview.isPending ? <Loader2 className="animate-spin" size={16} /> : null} Review understanding first
          </Button>
          <span className="text-xs text-muted">No further questions are asked. Typical run: 1–2 minutes{settings.data ? `, ≈ ${settings.data.estimate.typical} credits` : ""}.</span>
        </div>
      </Card>

      {preview.data && (
        <div className="mt-5">
          <BriefCard brief={preview.data.brief} values={overrides} onChange={setOverrides} estimate={preview.data.estimate} />
          {!preview.data.ready && <div className="mt-3"><Callout tone="warn" title="I could not recognise the country or sector">Mention both explicitly (e.g. “entry into Germany … logistics companies”). The mission would stop rather than guess.</Callout></div>}
        </div>
      )}

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {[
          { i: ScanSearch, t: "Find and size", d: "Searches Crustdata's company graph with exact, recorded filters. Market size = observed indexed count × your ACV, never a made-up TAM." },
          { i: Users, t: "Buyers and competitors", d: "Verified decision-makers matched to each account by company ID, plus a conservative competitor scan with confirmed vs possible labels." },
          { i: FileCheck2, t: "Audit every claim", d: "A verifier re-opens the saved source for each fact, flags stale or conflicting data, and recomputes all numbers. Unknowns stay unknown." },
        ].map((x) => (
          <Card key={x.t} className="p-5"><x.i className="text-brand" size={22} /><div className="mt-3 text-sm font-semibold">{x.t}</div><p className="mt-1 text-sm text-muted">{x.d}</p></Card>
        ))}
      </div>
    </div>
  );
}
