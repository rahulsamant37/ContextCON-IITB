import Link from "next/link";

export function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden>
      <defs><linearGradient id="me-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#6366f1" /><stop offset="1" stopColor="#14b8a6" /></linearGradient></defs>
      <rect width="28" height="28" rx="7" fill="url(#me-g)" />
      <path d="M7 18.5 11.5 13l3.5 3.5L21 9.5" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="21" cy="9.5" r="1.8" fill="#fff" />
    </svg>
  );
}

export function Wordmark({ href = "/", tone = "dark" }: { href?: string; tone?: "dark" | "light" }) {
  return (
    <Link href={href} className="flex items-center gap-2.5">
      <Mark /><span className={`text-[16px] font-semibold tracking-tight ${tone === "light" ? "text-white" : "text-ink"}`}>MarketEntry</span>
    </Link>
  );
}
