import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Wordmark } from "./brand";

export function LandingNav() {
  return (
    <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
      <Wordmark tone="light" />
      <nav className="hidden items-center gap-8 text-sm font-medium text-slate-200 md:flex" aria-label="Main">
        <a href="#how" className="hover:text-white">How it works</a><a href="#features" className="hover:text-white">Features</a>
        <a href="#trust" className="hover:text-white">Trust</a><a href="#faq" className="hover:text-white">FAQ</a>
      </nav>
      <Link href="/research" className="inline-flex h-9 items-center gap-1.5 rounded-md bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-slate-100" data-testid="nav-open-app">
        Open app<ArrowRight size={15} /></Link>
    </header>
  );
}

export function LandingCta({ compact = false }: { compact?: boolean }) {
  return (<>
    <Link href="/research/new" data-testid="hero-cta"
      className="inline-flex h-12 items-center gap-2 rounded-lg bg-indigo-500 px-6 text-[15px] font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-400">
      Start researching<ArrowRight size={17} /></Link>
    {!compact && <Link href="/research/new?example=germany" className="inline-flex h-12 items-center rounded-lg border border-white/25 px-6 text-[15px] font-medium text-white hover:bg-white/10">Try the free demo</Link>}
  </>);
}
