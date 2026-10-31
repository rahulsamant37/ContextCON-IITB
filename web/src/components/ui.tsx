"use client";
import clsx from "clsx";
import { Info, X } from "lucide-react";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral" | "accent";

const btn = (variant: string, size: string) => clsx(
  "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap",
  size === "sm" ? "h-8 px-3 text-[13px]" : size === "lg" ? "h-11 px-5 text-[15px]" : "h-9 px-3.5 text-sm",
  variant === "primary" && "bg-primary text-primary-ink hover:opacity-90",
  variant === "secondary" && "border border-line-strong bg-surface text-ink hover:bg-subtle",
  variant === "ghost" && "text-ink-2 hover:bg-subtle hover:text-ink",
  variant === "accent" && "bg-accent text-white hover:opacity-90 dark:text-[#0b0d10]",
);
type BtnProps = { variant?: "primary" | "secondary" | "ghost" | "accent"; size?: "sm" | "md" | "lg" };
export function Button({ variant = "primary", size = "md", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & BtnProps) {
  return <button {...p} className={clsx(btn(variant, size), className)} />;
}
export function LinkButton({ href, variant = "primary", size = "md", className, children, ...p }: { href: string; children: ReactNode; className?: string } & BtnProps & React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <Link href={href} {...p} className={clsx(btn(variant, size), className)}>{children}</Link>;
}

export function Card({ className, children, ...p }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <section {...p} className={clsx("rounded-lg border border-line bg-surface", className)}>{children}</section>;
}
export function CardHeader({ title, description, action }: { title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div className="min-w-0"><h2 className="text-[15px] font-semibold text-ink">{title}</h2>{description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, description, actions, crumbs, meta }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; crumbs?: { href?: string; label: string }[]; meta?: ReactNode }) {
  return (
    <div className="mb-6">
      {crumbs && <nav aria-label="Breadcrumb" className="mb-2 flex items-center gap-1.5 text-[13px] text-muted">{crumbs.map((c, i) => (
        <span key={i} className="flex items-center gap-1.5">{i > 0 && <span aria-hidden>/</span>}{c.href ? <Link className="hover:text-ink" href={c.href}>{c.label}</Link> : <span className="text-ink-2">{c.label}</span>}</span>))}</nav>}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2.5"><h1 className="text-[22px] font-semibold tracking-tight text-ink">{title}</h1>{meta}</div>
          {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}</div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

const PILL: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad", info: "bg-info-soft text-info",
  neutral: "bg-subtle text-ink-2", accent: "bg-accent-soft text-accent",
};
const DOT: Record<Tone, string> = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", info: "bg-info", neutral: "bg-muted", accent: "bg-accent" };
export function Pill({ tone = "neutral", children, title, dot = true, className }: { tone?: Tone; children: ReactNode; title?: string; dot?: boolean; className?: string }) {
  return (
    <span title={title} className={clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", PILL[tone], className)}>
      {dot && <span className={clsx("h-1.5 w-1.5 rounded-full", DOT[tone])} />}{children}
    </span>
  );
}

export function Bar({ value, max = 100, unknown, tone = "accent", className }: { value: number | null; max?: number; unknown?: boolean; tone?: Tone; className?: string }) {
  if (value == null || unknown) return <div className={clsx("bar-unknown h-1.5 w-full rounded-full bg-subtle", className)} title="Not available" />;
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-subtle", className)} role="meter" aria-valuenow={value} aria-valuemax={max}>
      <div className={clsx("h-full rounded-full", { accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", info: "bg-info", neutral: "bg-muted" }[tone])} style={{ width: `${w}%` }} />
    </div>
  );
}

export function Metric({ label, value, help, sub }: { label: string; value: ReactNode; help?: string; sub?: ReactNode }) {
  return (
    <div className="px-5 py-4">
      <div className="flex items-center gap-1 text-[13px] text-muted">{label}{help && <InfoTip text={help} />}</div>
      <div className="tabular mt-1 text-2xl font-semibold tracking-tight text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export const InfoTip = ({ text }: { text: string }) => (
  <span className="inline-flex cursor-help text-muted" title={text} aria-label={text} tabIndex={0}><Info size={13} /></span>
);

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="-mb-px flex gap-6 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} data-testid={`tab-${t.id}`} onClick={() => onChange(t.id)}
          className={clsx("flex items-center gap-1.5 whitespace-nowrap border-b-2 pb-2.5 pt-1 text-sm font-medium transition-colors", value === t.id ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink")}>
          {t.label}{t.count != null && <span className="tabular rounded bg-subtle px-1.5 text-xs text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export const inputBase = "h-9 rounded-md border border-line-strong bg-surface px-3 text-sm text-ink shadow-[0_1px_0_rgba(0,0,0,0.02)] transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
export const inputCls = `${inputBase} w-full`;
export function Field({ label, hint, error, children, optional, htmlFor }: { label: string; hint?: ReactNode; error?: string; children: ReactNode; optional?: boolean; htmlFor?: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 flex items-center gap-1.5 text-[13px] font-medium text-ink-2">{label}{optional && <span className="font-normal text-muted">Optional</span>}</label>
      {children}
      {error ? <p className="mt-1 text-xs text-bad">{error}</p> : hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: { options: { id: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-md border border-line-strong bg-subtle p-0.5">
      {options.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={value === o.id} onClick={() => onChange(o.id)}
          className={clsx("rounded px-3 py-1.5 text-[13px] font-medium transition", value === o.id ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink")}>{o.label}</button>
      ))}
    </div>
  );
}

export function TagInput({ values, onChange, suggestions, placeholder, id }: { values: string[]; onChange: (v: string[]) => void; suggestions: string[]; placeholder?: string; id?: string }) {
  const [draft, setDraft] = useState("");
  const add = (v: string) => { const t = v.trim(); if (t && !values.some((x) => x.toLowerCase() === t.toLowerCase())) onChange([...values, t]); setDraft(""); };
  const rest = suggestions.filter((s) => !values.includes(s));
  return (
    <div>
      <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border border-line-strong bg-surface px-2 py-1.5 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20">
        {values.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 rounded bg-subtle px-2 py-0.5 text-[13px] text-ink">{v}
            <button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(values.filter((x) => x !== v))} className="text-muted hover:text-ink"><X size={12} /></button></span>))}
        <input id={id} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={values.length ? "" : placeholder}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(draft); } else if (e.key === "Backspace" && !draft && values.length) onChange(values.slice(0, -1)); }}
          onBlur={() => draft && add(draft)} className="min-w-[8rem] flex-1 bg-transparent px-1 text-sm outline-none" />
      </div>
      {rest.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{rest.slice(0, 10).map((s) => (
        <button key={s} type="button" onClick={() => add(s)} className="rounded-full border border-line px-2.5 py-0.5 text-xs text-ink-2 hover:border-line-strong hover:bg-subtle">+ {s}</button>))}</div>}
    </div>
  );
}

export const Skeleton = ({ className }: { className?: string }) => <div className={clsx("animate-pulse rounded-md bg-subtle", className)} />;

export function Notice({ tone = "info", title, children, action }: { tone?: Tone; title?: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={clsx("flex items-start gap-3 rounded-lg border px-4 py-3", {
      ok: "border-ok/25 bg-ok-soft", warn: "border-warn/25 bg-warn-soft", bad: "border-bad/25 bg-bad-soft", info: "border-info/20 bg-info-soft",
      neutral: "border-line bg-subtle", accent: "border-accent/25 bg-accent-soft" }[tone])}>
      <div className="min-w-0 flex-1">{title && <div className="text-sm font-medium text-ink">{title}</div>}{children && <div className="mt-0.5 text-[13px] text-ink-2">{children}</div>}</div>
      {action}
    </div>
  );
}

export const EmptyState = ({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) => (
  <div className="flex flex-col items-center rounded-lg border border-dashed border-line-strong bg-surface px-6 py-14 text-center">
    {icon && <div className="mb-3 text-muted">{icon}</div>}
    <div className="text-[15px] font-semibold text-ink">{title}</div>{children && <p className="mt-1 max-w-md text-sm text-muted">{children}</p>}{action && <div className="mt-5">{action}</div>}
  </div>
);

export function SidePanel({ open, onClose, title, subtitle, children, footer }: { open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/25 backdrop-blur-[1px]" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl" data-testid="drawer">
        <div className="flex items-start justify-between gap-3 border-b border-line px-6 py-4">
          <div className="min-w-0"><div className="text-base font-semibold text-ink">{title}</div>{subtitle && <div className="mt-0.5 text-[13px] text-muted">{subtitle}</div>}</div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1.5 text-muted hover:bg-subtle hover:text-ink"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="border-t border-line px-6 py-3">{footer}</div>}
      </div>
    </div>
  );
}

// ---- toasts -------------------------------------------------------------------------------------
type ToastItem = { id: number; text: string; tone: Tone };
const ToastCtx = createContext<(text: string, tone?: Tone) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((text: string, tone: Tone = "neutral") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 2600);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="pointer-events-auto rounded-md border border-line bg-surface px-4 py-2.5 text-sm text-ink shadow-lg">
            <span className={clsx("mr-2 inline-block h-2 w-2 rounded-full", DOT[t.tone])} />{t.text}</div>))}
      </div>
    </ToastCtx.Provider>
  );
}

export const th = "px-4 py-2.5 text-left text-xs font-medium text-muted";
export const td = "px-4 py-3 align-middle";
