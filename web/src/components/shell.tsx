"use client";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { LayoutGrid, Menu, Moon, Plus, Settings, Sun, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { api } from "@/lib/api";
import { Wordmark } from "./brand";
import { Notice, Skeleton } from "./ui";

const subscribeTheme = (cb: () => void) => {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => obs.disconnect();
};

function ThemeToggle() {
  // The <html> class is the source of truth (set before paint by the inline script in layout.tsx).
  const dark = useSyncExternalStore(subscribeTheme, () => document.documentElement.classList.contains("dark"), () => false);
  return (
    <button aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} title={dark ? "Light theme" : "Dark theme"} onClick={() => {
      document.documentElement.classList.toggle("dark", !dark);
      try { localStorage.setItem("theme", !dark ? "dark" : "light"); } catch {}
    }} className="rounded-md p-1.5 text-side-muted hover:bg-side-2 hover:text-side-ink">
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function NavLink({ href, icon: Icon, children, active, onClick }: { href: string; icon: typeof Plus; children: ReactNode; active: boolean; onClick?: () => void }) {
  return (
    <Link href={href} onClick={onClick} aria-current={active ? "page" : undefined}
      className={clsx("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors", active ? "bg-side-2 text-white" : "text-side-muted hover:bg-side-2 hover:text-side-ink")}>
      <Icon size={16} />{children}
    </Link>
  );
}

function GuestBadge() {
  return (
    <div className="flex items-center gap-2.5 rounded-md px-2 py-2" data-testid="guest-badge">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-indigo-500 to-teal-500 text-white"><UserRound size={16} /></span>
      <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium text-side-ink" data-testid="user-name">Guest</div>
        <div className="truncate text-xs text-side-muted">Your work is saved in this browser</div></div>
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const list = useQuery({ queryKey: ["history"], queryFn: api.list, staleTime: 10_000 });
  const recent = (list.data?.missions ?? []).filter((m) => m.industry && m.industry !== "unknown").slice(0, 6);
  return (
    <div className="flex h-full flex-col px-3 py-4">
      <div className="flex items-center justify-between px-2"><Wordmark href="/research" tone="light" /><ThemeToggle /></div>
      <Link href="/research/new" onClick={onNavigate} className="mt-6 flex h-9 items-center justify-center gap-1.5 rounded-md bg-primary text-sm font-medium text-white shadow-sm hover:bg-primary-strong" data-testid="nav-new">
        <Plus size={16} />New research</Link>
      <nav className="mt-5 space-y-0.5" aria-label="Main">
        <NavLink href="/research" icon={LayoutGrid} active={path === "/research"} onClick={onNavigate}>All research</NavLink>
        <NavLink href="/settings" icon={Settings} active={path.startsWith("/settings")} onClick={onNavigate}>Settings</NavLink>
      </nav>
      {recent.length > 0 && (
        <div className="mt-7">
          <div className="px-2.5 pb-2 text-[11px] font-semibold uppercase tracking-wider text-side-muted">Recent</div>
          <ul className="space-y-0.5">{recent.map((m) => {
            const href = `/research/${m.mission_id}`;
            return (
              <li key={m.mission_id}><Link href={href} onClick={onNavigate} className={clsx("flex items-center gap-2 truncate rounded-md px-2.5 py-1.5 text-[13px]", path.startsWith(href) ? "bg-side-2 text-white" : "text-side-muted hover:bg-side-2 hover:text-side-ink")}>
                <span className={clsx("h-1.5 w-1.5 shrink-0 rounded-full", m.state === "failed" ? "bg-red-400" : "bg-emerald-400")} /><span className="truncate">{m.industry} · {m.country}</span></Link></li>);
          })}</ul>
        </div>)}
      <div className="mt-auto border-t border-side-line pt-3"><GuestBadge /></div>
    </div>
  );
}

/** App area. No sign-in: the first request creates a private guest session (cookie) before anything else loads,
 * so parallel requests never race to create several guests. */
export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: 2 });

  if (me.isLoading) return <div className="grid min-h-screen place-items-center bg-page"><Skeleton className="h-8 w-40" /></div>;
  if (me.isError) return <div className="grid min-h-screen place-items-center bg-page p-6"><Notice tone="bad" title="Can't reach MarketEntry">Check that the server is running, then refresh this page.</Notice></div>;
  return (
    <div className="min-h-screen bg-page lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-side lg:block"><Sidebar /></aside>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 bg-side px-4 lg:hidden">
        <button aria-label="Open menu" onClick={() => setOpen(true)} className="rounded-md p-1.5 text-side-ink hover:bg-side-2"><Menu size={20} /></button><Wordmark href="/research" tone="light" />
      </header>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="relative h-full w-72 bg-side">
            <button aria-label="Close menu" onClick={() => setOpen(false)} className="absolute right-3 top-4 z-10 rounded-md p-1 text-side-ink hover:bg-side-2"><X size={18} /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>)}
      <main className="mx-auto w-full max-w-[1200px] px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}
