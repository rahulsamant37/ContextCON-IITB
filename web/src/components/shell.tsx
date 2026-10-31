"use client";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { LayoutGrid, Menu, Moon, Plus, Settings, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { api } from "@/lib/api";

const subscribeTheme = (cb: () => void) => {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => obs.disconnect();
};

function ThemeToggle() {
  // The <html> class is the source of truth (set before paint by the inline script in layout.tsx).
  const dark = useSyncExternalStore(subscribeTheme, () => document.documentElement.classList.contains("dark"), () => false);
  return (
    <button aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => {
      document.documentElement.classList.toggle("dark", !dark);
      try { localStorage.setItem("theme", !dark ? "dark" : "light"); } catch {}
    }} className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] text-muted hover:bg-subtle hover:text-ink">
      {dark ? <Sun size={15} /> : <Moon size={15} />}{dark ? "Light theme" : "Dark theme"}
    </button>
  );
}

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-2.5">
      <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden className="text-ink"><rect width="24" height="24" rx="6" fill="currentColor" />
        <path d="M6 16.5 10 12l3 3 5-6.5" stroke="var(--surface)" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <span className="text-[15px] font-semibold tracking-tight text-ink">MarketEntry</span>
    </Link>
  );
}

function NavLink({ href, icon: Icon, children, active, onClick }: { href: string; icon: typeof Plus; children: ReactNode; active: boolean; onClick?: () => void }) {
  return (
    <Link href={href} onClick={onClick} aria-current={active ? "page" : undefined}
      className={clsx("flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium", active ? "bg-subtle text-ink" : "text-ink-2 hover:bg-subtle hover:text-ink")}>
      <Icon size={16} className={active ? "text-ink" : "text-muted"} />{children}
    </Link>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const list = useQuery({ queryKey: ["history"], queryFn: api.list, staleTime: 10_000 });
  const health = useQuery({ queryKey: ["settings"], queryFn: api.settings, retry: false });
  const recent = list.data?.missions.slice(0, 6) ?? [];
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-4">
      <Logo />
      <Link href="/new" onClick={onNavigate} className="mx-1 flex h-9 items-center justify-center gap-1.5 rounded-md bg-primary text-sm font-medium text-primary-ink hover:opacity-90" data-testid="nav-new">
        <Plus size={16} />New research</Link>
      <nav className="space-y-0.5" aria-label="Main">
        <NavLink href="/" icon={LayoutGrid} active={path === "/"} onClick={onNavigate}>All research</NavLink>
        <NavLink href="/settings" icon={Settings} active={path.startsWith("/settings")} onClick={onNavigate}>Settings</NavLink>
      </nav>
      {recent.length > 0 && (
        <div>
          <div className="px-2.5 pb-1.5 text-xs font-medium text-muted">Recent</div>
          <ul className="space-y-0.5">{recent.map((m) => {
            const href = `/missions/${m.mission_id}`;
            return (
              <li key={m.mission_id}><Link href={href} onClick={onNavigate} className={clsx("block truncate rounded-md px-2.5 py-1.5 text-[13px]", path.startsWith(href) ? "bg-subtle text-ink" : "text-ink-2 hover:bg-subtle")}>
                {m.industry && m.industry !== "unknown" ? `${m.industry} · ${m.country}` : "Unrecognised request"}</Link></li>);
          })}</ul>
        </div>)}
      <div className="mt-auto space-y-1">
        <ThemeToggle />
        <div className="flex items-center gap-2 px-2.5 text-xs text-muted">
          <span className={clsx("h-1.5 w-1.5 rounded-full", health.isError ? "bg-bad" : health.data ? "bg-ok" : "bg-muted")} />
          {health.isError ? "Server unreachable" : health.data ? "Connected" : "Connecting…"}
        </div>
      </div>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen lg:pl-60">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-line bg-surface lg:block"><Sidebar /></aside>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface px-4 lg:hidden">
        <button aria-label="Open menu" onClick={() => setOpen(true)} className="rounded-md p-1.5 hover:bg-subtle"><Menu size={20} /></button><Logo />
      </header>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <aside className="relative h-full w-64 border-r border-line bg-surface">
            <button aria-label="Close menu" onClick={() => setOpen(false)} className="absolute right-3 top-4 rounded-md p-1 hover:bg-subtle"><X size={18} /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>)}
      <main className="mx-auto w-full max-w-[1180px] px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}
