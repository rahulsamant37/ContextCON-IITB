"use client";
import clsx from "clsx";
import { X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";

export function Button({ variant = "primary", size = "md", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" | "lg" }) {
  return (
    <button
      {...p}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" && "px-2.5 py-1 text-sm", size === "md" && "px-4 py-2 text-sm", size === "lg" && "px-6 py-3 text-base",
        variant === "primary" && "bg-brand text-white hover:opacity-90 dark:text-[#0d1117]",
        variant === "secondary" && "border border-border bg-surface hover:bg-surface-2",
        variant === "ghost" && "hover:bg-surface-2",
        variant === "danger" && "bg-bad text-white hover:opacity-90",
        className,
      )}
    />
  );
}

export function Card({ className, children, ...p }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div {...p} className={clsx("rounded-xl border border-border bg-surface shadow-sm", className)}>{children}</div>;
}
export const CardHeader = ({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) => (
  <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-3.5">
    <div><h3 className="text-sm font-semibold">{title}</h3>{sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}</div>{right}
  </div>
);

const TONES = {
  neutral: "bg-surface-2 text-muted", brand: "bg-brand-soft text-brand", good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad",
} as const;
export type Tone = keyof typeof TONES;
export const Badge = ({ tone = "neutral", children, title, className }: { tone?: Tone; children: ReactNode; title?: string; className?: string }) => (
  <span title={title} className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", TONES[tone], className)}>{children}</span>
);

export function Meter({ value, max = 100, tone = "brand", unknown, label }: { value: number | null; max?: number; tone?: Tone; unknown?: boolean; label?: string }) {
  if (value == null || unknown) {
    return <div className="unknown-hatch h-2 w-full rounded-full border border-border" title={label ?? "unknown: no observed evidence"} aria-label="unknown" />;
  }
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2" role="meter" aria-valuenow={value} aria-valuemax={max} title={label}>
      <div className={clsx("h-full rounded-full", tone === "good" ? "bg-good" : tone === "warn" ? "bg-warn" : tone === "bad" ? "bg-bad" : "bg-brand")} style={{ width: `${w}%` }} />
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={clsx("mt-1 text-2xl font-semibold tabular-nums", tone === "warn" && "text-warn", tone === "bad" && "text-bad", tone === "good" && "text-good")}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </Card>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-border">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} data-testid={`tab-${t.id}`} onClick={() => onChange(t.id)}
          className={clsx("whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition", value === t.id ? "border-brand text-brand" : "border-transparent text-muted hover:text-text")}>
          {t.label}{t.count != null && <span className="ml-1.5 rounded-full bg-surface-2 px-1.5 py-0.5 text-xs">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export const Skeleton = ({ className }: { className?: string }) => <div className={clsx("animate-pulse rounded-lg bg-surface-2", className)} />;

export function Callout({ tone = "neutral", title, children }: { tone?: Tone; title?: ReactNode; children?: ReactNode }) {
  const ring = { neutral: "border-border", brand: "border-brand", good: "border-good", warn: "border-warn", bad: "border-bad" }[tone];
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={clsx("rounded-xl border-l-4 bg-surface px-4 py-3 shadow-sm", ring, "border-y border-r border-y-border border-r-border")}>
      {title && <div className="text-sm font-semibold">{title}</div>}{children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

export const Empty = ({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) => (
  <div className="rounded-xl border border-dashed border-border p-10 text-center">
    <div className="text-sm font-semibold">{title}</div>{children && <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p>}{action && <div className="mt-4">{action}</div>}
  </div>
);

export function Drawer({ open, onClose, title, children, width = "max-w-2xl" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className={clsx("relative flex h-full w-full flex-col bg-bg shadow-2xl", width)} data-testid="drawer">
        <div className="flex items-center justify-between border-b border-border bg-surface px-5 py-3">
          <div className="min-w-0 text-base font-semibold">{title}</div>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 hover:bg-surface-2"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

export const statusTone = (s: string): Tone =>
  ({ supported: "good", stale: "warn", unverified: "warn", conflicting: "bad", unsupported: "bad" } as Record<string, Tone>)[s] ?? "neutral";
export const waveTone = (w: string | null): Tone => (w === "Wave 1" ? "good" : w === "Wave 2" ? "brand" : w === "Research Needed" ? "warn" : "neutral");
