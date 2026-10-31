export const UNKNOWN = "Not available";
export const num = (v: number | null | undefined, d = 0) => (v == null ? UNKNOWN : v.toLocaleString("en-US", { maximumFractionDigits: d }));
export const pct = (v: number | null | undefined, d = 1) => (v == null ? UNKNOWN : `${v > 0 ? "+" : ""}${v.toFixed(d)}%`);
export function money(v: number | null | undefined, cur?: string | null, compact = false) {
  if (v == null) return UNKNOWN;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD", maximumFractionDigits: compact ? 1 : 0, notation: compact ? "compact" : "standard" }).format(v);
  } catch { return `${cur ?? ""} ${v.toLocaleString("en-US")}`.trim(); }
}
export function ago(iso: string | null | undefined) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "Just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

// Plain-language names for engine concepts (the engine keeps its own identifiers).
export const PRIORITY: Record<string, { label: string; tone: "ok" | "info" | "warn" | "neutral"; help: string }> = {
  "Wave 1": { label: "Contact first", tone: "ok", help: "Strong fit and a verified decision-maker." },
  "Wave 2": { label: "Next in line", tone: "info", help: "Good fit; a contact still needs to be found or confirmed." },
  "Research Needed": { label: "Needs research", tone: "warn", help: "Too little data, or the company could not be confirmed." },
};
export const priority = (w: string | null) => (w ? PRIORITY[w] : { label: "Outside target", tone: "neutral" as const, help: "Outside the size or country you asked for." });
export const CONTACT: Record<string, { label: string; tone: "ok" | "warn" | "neutral" }> = {
  found: { label: "Found", tone: "ok" }, buyer_not_found: { label: "None found", tone: "warn" }, not_searched: { label: "Not searched", tone: "neutral" },
};
export const STEP_LABEL: Record<string, string> = {
  A_brief: "Reading your brief", B_discovery: "Finding companies", C_enrichment: "Collecting company details",
  E_buyers: "Finding decision-makers", D_competitors: "Checking competitors", F_sizing: "Estimating market value",
  G_verification: "Checking every fact against its source", H_execution: "Preparing your report and pipeline",
};
export const STEP_DETAIL: Record<string, string> = {
  A_brief: "Understanding the market, company size, deal size and buyer roles.",
  B_discovery: "Searching Crustdata's company database with your filters.",
  C_enrichment: "Pulling headcount, growth, hiring and funding for the best matches.",
  E_buyers: "Looking for people in your buyer roles and confirming where they work.",
  D_competitors: "Searching for companies that sell something similar.",
  F_sizing: "Multiplying the number of matching companies by your deal size.",
  G_verification: "Re-opening every saved source to confirm each number.",
  H_execution: "Building the report, files and your pipeline with draft messages.",
};
export const STEP_ORDER = ["A_brief", "B_discovery", "C_enrichment", "E_buyers", "D_competitors", "F_sizing", "G_verification", "H_execution"];
export const COMPONENT_LABEL: Record<string, string> = {
  icp_country: "In your target country", icp_headcount: "Right company size", icp_sector: "In your sector", growth: "Team is growing",
  hiring: "Actively hiring", need: "Relevant to your product", buyer: "Decision-maker found",
};
export const STATE: Record<string, { label: string; tone: "ok" | "warn" | "bad" }> = {
  completed: { label: "Complete", tone: "ok" }, completed_with_warnings: { label: "Complete", tone: "ok" },
  partial: { label: "Partially complete", tone: "warn" }, failed: { label: "Could not complete", tone: "bad" },
};
export const SOURCE_STATUS: Record<string, { label: string; tone: "ok" | "warn" | "bad" }> = {
  supported: { label: "Confirmed", tone: "ok" }, unverified: { label: "Not checked", tone: "warn" }, stale: { label: "Outdated", tone: "warn" },
  conflicting: { label: "Conflicting", tone: "bad" }, unsupported: { label: "Not confirmed", tone: "bad" },
};
export const COMPETITOR: Record<string, { label: string; tone: "bad" | "warn" | "neutral"; help: string }> = {
  confirmed: { label: "Direct competitor", tone: "bad", help: "Their description matches your category and independent web results mention them." },
  possible: { label: "Possible competitor", tone: "warn", help: "One of the two signals is present." },
  insufficient_evidence: { label: "Unclear", tone: "neutral", help: "Not enough public information to tell." },
};
export const sentenceCase = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
export const score = (v: number | null | undefined) => (v == null ? "—" : String(Math.round(v)));
