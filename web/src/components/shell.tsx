"use client";
import clsx from "clsx";
import { BarChart3, History, Moon, Plus, Settings, ShieldCheck, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore, type ReactNode } from "react";

const NAV = [
  { href: "/", label: "New mission", icon: Plus },
  { href: "/history", label: "Missions", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

const subscribeTheme = (cb: () => void) => {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => obs.disconnect();
};

function ThemeToggle() {
  // The <html> class is the source of truth (set before paint by the inline script in layout.tsx).
  const dark = useSyncExternalStore(subscribeTheme, () => document.documentElement.classList.contains("dark"), () => false);
  return (
    <button aria-label="Toggle dark mode" onClick={() => {
      const next = !dark;
      document.documentElement.classList.toggle("dark", next);
      try { localStorage.setItem("theme", next ? "dark" : "light"); } catch {}
    }} className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-text">
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand text-white dark:text-[#0d1117]"><BarChart3 size={16} /></span>
            MarketEntryOS
          </Link>
          <nav className="flex flex-1 items-center gap-1" aria-label="Main">
            {NAV.map((n) => {
              const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
              return (
                <Link key={n.href} href={n.href} className={clsx("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium", active ? "bg-brand-soft text-brand" : "text-muted hover:bg-surface-2 hover:text-text")}>
                  <n.icon size={15} />{n.label}
                </Link>
              );
            })}
          </nav>
          <span className="hidden items-center gap-1.5 text-xs text-muted sm:flex"><ShieldCheck size={14} className="text-good" />Every claim cited · nothing sent</span>
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
      <footer className="border-t border-border py-4 text-center text-xs text-muted">
        Counts are Crustdata-indexed, not the whole market. Market size = observed count × your ACV: illustrative, not forecast revenue. Outreach is drafted locally and never sent.
      </footer>
    </div>
  );
}
