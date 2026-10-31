import { Building2, Check, CheckCircle2, FileSpreadsheet, FileText, KanbanSquare, Layers, Search, ShieldCheck, Swords, UserCheck, Wallet } from "lucide-react";
import Link from "next/link";
import { Mark } from "@/components/brand";
import { LandingCta, LandingNav } from "@/components/landing-auth";

const FEATURES = [
  { icon: Building2, title: "Companies worth approaching", text: "A ranked shortlist of companies in your country, industry and size range, scored on fit, growth and hiring." },
  { icon: UserCheck, title: "The people who decide", text: "Decision-makers in the roles you sell to, with their current employer confirmed, not guessed from a name." },
  { icon: Swords, title: "Who you're up against", text: "Competitors in your category, labelled direct or possible based on what they say and what the web says about them." },
  { icon: Wallet, title: "What the market is worth", text: "A transparent estimate: companies found × your contract value, with every input shown so you can defend it." },
  { icon: ShieldCheck, title: "A source behind every number", text: "Each fact links to the exact record it came from. Missing data is marked as missing, never filled in." },
  { icon: KanbanSquare, title: "A pipeline you can work", text: "Companies and contacts land in a ready-made pipeline with draft messages that you review and send yourself." },
];

const FAQ = [
  ["Where does the data come from?", "Company and people data comes from Crustdata's live database of companies and professional profiles. Competitor checks also use live web search. Every fact in your results links to its source record."],
  ["Do you contact anyone on my behalf?", "Never. Draft messages are saved in your pipeline for you to review, edit and send from your own email. There is no send button."],
  ["How accurate is the market value?", "It is the number of matching companies multiplied by the contract value you enter, so it is only as good as those inputs. We show both, and we never present it as a revenue forecast."],
  ["How long does a research take?", "Usually about a minute. You can watch each step as it happens, and close the page; the research keeps running."],
  ["What if information is missing?", "We show it as “Not available” and score the company only on what we could confirm. Missing data lowers data completeness, not the company's score."],
  ["Who can see my research?", "Only you. Each account's research, pipeline and files are private to that account."],
];

function ProductPreview() {
  const rows = [
    ["United Heavy Lift GmbH & Co. KG", "128", "Contact first", 77],
    ["DGL Deutsche Getränke Logistik", "146", "Contact first", 67],
    ["BCL – Building Construction Logistics", "103", "Next in line", 59],
    ["LOXXESS Gruppe", "382", "Next in line", 59],
  ] as const;
  return (
    <div className="relative mx-auto mt-16 max-w-5xl [animation-delay:200ms]">
      <div className="absolute -inset-x-6 -bottom-6 top-10 rounded-[28px] bg-gradient-to-r from-indigo-500/25 via-violet-500/10 to-teal-400/25 blur-2xl" aria-hidden />
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-white shadow-2xl shadow-indigo-950/40">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" /><span className="h-2.5 w-2.5 rounded-full bg-amber-400" /><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <span className="ml-3 text-xs text-slate-500">MarketEntry · Logistics in Germany</span>
        </div>
        <div className="flex">
          <div className="hidden w-44 shrink-0 flex-col gap-1.5 bg-[#0b1220] p-3 sm:flex" aria-hidden>
            <div className="flex items-center gap-2 px-1 pb-3"><Mark size={18} /><span className="text-xs font-semibold text-white">MarketEntry</span></div>
            <div className="rounded bg-indigo-500 px-2 py-1.5 text-center text-[11px] font-medium text-white">New research</div>
            {["All research", "Logistics · Germany", "FinTech · United Kingdom", "Healthcare · India"].map((x, i) => (
              <div key={x} className={`rounded px-2 py-1.5 text-[11px] ${i === 1 ? "bg-white/10 text-white" : "text-slate-400"}`}>{x}</div>))}
          </div>
          <div className="min-w-0 flex-1 space-y-3 bg-[#f5f6fa] p-4 text-left sm:p-5">
            <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-[12px]"><b className="text-slate-900">Promising: confirm decision-makers first.</b> <span className="text-slate-600">413 logistics companies found in your size range.</span></div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[["Companies found", "413"], ["Ready to contact", "2"], ["Decision-makers", "2"], ["Market value", "€3.7M"]].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-slate-200 bg-white px-3 py-2"><div className="text-[10px] text-slate-500">{k}</div><div className="text-lg font-semibold text-slate-900">{v}</div></div>))}
            </div>
            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-3 py-2 text-[12px] font-semibold text-slate-900">Top companies to approach</div>
              {rows.map(([n, e, p, s]) => (
                <div key={n} className="flex items-center gap-3 border-b border-slate-100 px-3 py-2 text-[12px] last:border-0">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded bg-slate-100 text-[10px] font-semibold text-slate-600">{n[0]}</span>
                  <span className="min-w-0 flex-1 truncate text-slate-900">{n}<span className="ml-2 text-slate-400">{e} employees</span></span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${p === "Contact first" ? "bg-emerald-50 text-emerald-700" : "bg-sky-50 text-sky-700"}`}>{p}</span>
                  <span className="hidden w-20 sm:block"><span className="block h-1.5 rounded-full bg-slate-100"><span className="block h-1.5 rounded-full bg-indigo-500" style={{ width: `${s}%` }} /></span></span>
                  <span className="w-6 text-right font-semibold text-slate-900">{s}</span>
                </div>))}
            </div>
          </div>
        </div>
      </div>
      <p className="relative mt-4 text-center text-xs text-slate-300">Sample from a real research run. Company data via Crustdata.</p>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="bg-page text-ink">
      {/* hero */}
      <section className="hero-bg relative overflow-hidden pb-24">
        <div className="grid-lines absolute inset-0" aria-hidden />
        <LandingNav />
        <div className="relative mx-auto max-w-6xl px-6 pt-16 text-center sm:pt-24">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-slate-100">
            <span className="rounded-full bg-primary-soft0 px-1.5 py-0.5 text-[10px] font-semibold text-white">NEW</span>Live company and people data, checked fact by fact</div>
          <h1 className="mx-auto mt-6 max-w-4xl text-4xl font-semibold leading-[1.08] tracking-tight text-white [animation-delay:60ms] sm:text-6xl">
            Size up a new market <span className="text-gradient">before you bet on it</span></h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-200 [animation-delay:120ms]">
            Tell MarketEntry what you sell and where. In about a minute you get the companies to target, the people who decide, your competitors and what the market is worth, with a source behind every number.</p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3 [animation-delay:160ms]"><LandingCta /></div>
          <ul className="mt-7 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-slate-300 [animation-delay:200ms]">
            {["No sign-up needed", "Results in about a minute", "Nothing is ever sent for you"].map((x) => <li key={x} className="flex items-center gap-1.5"><Check size={15} className="text-teal-400" />{x}</li>)}
          </ul>
          <ProductPreview />
        </div>
      </section>

      {/* data strip */}
      <section className="border-b border-line bg-subtle">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-10 text-center sm:grid-cols-3">
          {[["200M+ companies", "searchable through Crustdata*"], ["800M+ professional profiles", "to find decision-makers*"], ["Every fact checked", "against the saved source record"]].map(([a, b]) => (
            <div key={a}><div className="text-2xl font-semibold tracking-tight text-ink">{a}</div><div className="mt-1 text-sm text-muted">{b}</div></div>))}
        </div>
        <p className="pb-6 text-center text-[11px] text-muted">*Coverage figures as published by Crustdata.</p>
      </section>

      {/* how it works */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24">
        <div className="mx-auto max-w-2xl text-center">
          <div className="text-sm font-semibold text-primary">How it works</div>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">From a question to a pipeline in three steps</h2>
          <p className="mt-4 text-ink-2">No spreadsheets, no scraping, no guesswork. You describe the market; MarketEntry does the desk research a consultant would do.</p>
        </div>
        <div className="mt-14 grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-line p-6">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary">1</div>
            <h3 className="mt-4 text-lg font-semibold">Describe your market</h3><p className="mt-2 text-sm text-ink-2">Pick a country and industry, set the company size and your deal value, and add the job titles you sell to.</p>
            <div className="mt-5 flex flex-wrap gap-1.5" aria-hidden>{["Germany", "Logistics", "100–1,000 employees", "€9,000 / year", "CTO", "Head of Fleet"].map((x) => <span key={x} className="rounded-md border border-line bg-subtle px-2 py-1 text-xs text-ink-2">{x}</span>)}</div>
          </div>
          <div className="rounded-2xl border border-line p-6">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary">2</div>
            <h3 className="mt-4 text-lg font-semibold">We research it, live</h3><p className="mt-2 text-sm text-ink-2">Watch each step: finding companies, collecting details, confirming decision-makers, checking competitors and verifying every number.</p>
            <ul className="mt-5 space-y-2 text-xs" aria-hidden>{["Finding companies", "Finding decision-makers", "Checking every fact"].map((x, i) => (
              <li key={x} className="flex items-center gap-2"><CheckCircle2 size={15} className={i < 2 ? "text-emerald-500" : "text-indigo-400"} /><span className="text-ink-2">{x}</span></li>))}</ul>
          </div>
          <div className="rounded-2xl border border-line p-6">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary">3</div>
            <h3 className="mt-4 text-lg font-semibold">Act on the results</h3><p className="mt-2 text-sm text-ink-2">Read the recommendation, download the report and spreadsheets, and work the pipeline with ready-to-edit draft messages.</p>
            <div className="mt-5 grid grid-cols-3 gap-1.5" aria-hidden>{["New", "Contacted", "Meeting"].map((x, i) => (
              <div key={x} className="rounded-md bg-subtle p-1.5"><div className="text-[10px] font-medium text-muted">{x}</div><div className="mt-1 h-5 rounded bg-surface shadow-sm" />{i < 2 && <div className="mt-1 h-5 rounded bg-surface shadow-sm" />}</div>))}</div>
          </div>
        </div>
      </section>

      {/* features */}
      <section id="features" className="scroll-mt-20 bg-subtle py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="max-w-2xl">
            <div className="text-sm font-semibold text-primary">What you get</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Everything a market-entry study needs, in one place</h2>
          </div>
          <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-surface p-7">
                <div className="grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-primary-soft to-subtle text-primary"><f.icon size={20} /></div>
                <h3 className="mt-5 font-semibold">{f.title}</h3><p className="mt-2 text-sm leading-relaxed text-ink-2">{f.text}</p>
              </div>))}
          </div>
        </div>
      </section>

      {/* trust */}
      <section id="trust" className="scroll-mt-20 py-24">
        <div className="mx-auto grid max-w-6xl items-center gap-14 px-6 lg:grid-cols-2">
          <div>
            <div className="text-sm font-semibold text-primary">Built to be trusted</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Every number comes with a receipt</h2>
            <p className="mt-4 text-ink-2">Before you see a result, MarketEntry re-opens the original data for every fact and confirms the value is really there. Anything it can&apos;t confirm is flagged, not hidden.</p>
            <ul className="mt-8 space-y-4">{[
              ["No made-up numbers", "AI helps read your brief and polish wording. It never produces a figure or a fact."],
              ["Unknowns stay unknown", "Missing data is shown as missing and never counted against a company."],
              ["You stay in control", "Nothing is sent to anyone. Drafts wait in your pipeline for you."],
              ["Private to you", "Your research, pipeline and files are visible only in your browser session."]].map(([t, d]) => (
              <li key={t} className="flex gap-3"><CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-500" /><div><div className="font-medium">{t}</div><div className="text-sm text-ink-2">{d}</div></div></li>))}</ul>
          </div>
          <div className="relative">
            <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-primary-soft via-surface to-subtle" aria-hidden />
            <div className="relative rounded-2xl border border-line bg-surface p-6 shadow-xl shadow-black/5">
              <div className="flex items-center justify-between"><div className="text-sm font-semibold">Headcount: 128</div><span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />Confirmed</span></div>
              <p className="mt-1 text-xs text-muted">We re-opened the saved data and found exactly this value for this company.</p>
              <dl className="mt-5 grid grid-cols-[9rem_1fr] gap-y-2.5 rounded-lg bg-subtle p-4 text-[13px]">
                <dt className="text-muted">Company</dt><dd>United Heavy Lift GmbH &amp; Co. KG</dd>
                <dt className="text-muted">Value we used</dt><dd className="font-medium">128</dd>
                <dt className="text-muted">Value in source</dt><dd className="flex items-center gap-1.5 font-medium">128 <CheckCircle2 size={14} className="text-emerald-500" /></dd>
                <dt className="text-muted">Data source</dt><dd>Crustdata · <span className="font-mono text-xs">headcount.total</span></dd>
                <dt className="text-muted">Retrieved</dt><dd>31 Oct 2026, 11:54</dd>
              </dl>
              <div className="mt-4 flex items-center gap-2 text-xs text-muted"><Layers size={14} />1 of 1,176 facts checked in this research, 100% confirmed</div>
            </div>
          </div>
        </div>
      </section>

      {/* deliverables */}
      <section className="bg-[#0b1220] py-24 text-white">
        <div className="mx-auto max-w-6xl px-6">
          <div className="max-w-2xl"><div className="text-sm font-semibold text-indigo-300">Deliverables</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Ready to share with your team or your board</h2></div>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[[FileText, "Market entry report", "PDF with the recommendation, target companies, competitors, market value, assumptions and next steps."],
              [FileSpreadsheet, "Target companies", "Spreadsheet of ranked companies with scores, data completeness and sources."],
              [UserCheck, "Decision-makers", "People in your buyer roles with confirmed employers. No scraped emails."],
              [KanbanSquare, "Sales pipeline", "Stages, tasks and draft messages, ready for your team to work."]].map(([Icon, t, d]) => {
              const I = Icon as typeof FileText;
              return <div key={t as string} className="rounded-xl border border-white/10 bg-white/[0.03] p-6"><I size={22} className="text-indigo-300" /><div className="mt-4 font-semibold">{t as string}</div><p className="mt-2 text-sm text-slate-300">{d as string}</p></div>;
            })}
          </div>
        </div>
      </section>

      {/* faq */}
      <section id="faq" className="mx-auto max-w-3xl scroll-mt-20 px-6 py-24">
        <h2 className="text-center text-3xl font-semibold tracking-tight">Questions, answered</h2>
        <div className="mt-10 divide-y divide-line rounded-2xl border border-line">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group px-6 py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">{q}<span className="text-xl leading-none text-muted transition group-open:rotate-45">+</span></summary>
              <p className="mt-3 text-sm leading-relaxed text-ink-2">{a}</p>
            </details>))}
        </div>
      </section>

      {/* cta */}
      <section className="px-6 pb-24">
        <div className="hero-bg relative mx-auto max-w-6xl overflow-hidden rounded-3xl px-8 py-16 text-center">
          <div className="grid-lines absolute inset-0" aria-hidden />
          <div className="relative">
            <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Your next market, researched by lunch</h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-200">No sign-up needed. Run the free demo, or research your own market in about a minute.</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3"><LandingCta compact /></div>
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8 text-sm text-muted">
          <div className="flex items-center gap-2.5"><Mark size={20} /><span className="font-medium text-ink-2">MarketEntry</span><span>© 2026</span></div>
          <nav className="flex gap-6" aria-label="Footer"><a href="#how" className="hover:text-ink">How it works</a><a href="#features" className="hover:text-ink">Features</a><a href="#faq" className="hover:text-ink">FAQ</a><Link href="/research" className="hover:text-ink">Open app</Link></nav>
          <div className="flex items-center gap-1.5">Company and people data by Crustdata<Search size={13} /></div>
        </div>
      </footer>
    </div>
  );
}

