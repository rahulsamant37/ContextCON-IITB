export const UNKNOWN = "unknown";
export const num = (v: number | null | undefined, d = 0) => (v == null ? UNKNOWN : v.toLocaleString("en-US", { maximumFractionDigits: d }));
export const pct = (v: number | null | undefined, d = 1) => (v == null ? UNKNOWN : `${v.toFixed(d)}%`);
export function money(v: number | null | undefined, cur?: string | null) {
  if (v == null) return UNKNOWN;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD", maximumFractionDigits: 0 }).format(v);
  } catch { return `${cur ?? ""} ${v.toLocaleString("en-US")}`.trim(); }
}
export function ago(iso: string | null | undefined) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}
export const STEP_LABEL: Record<string, string> = {
  A_brief: "Understand request", B_discovery: "Find companies", C_enrichment: "Enrich top accounts",
  E_buyers: "Map buyers", D_competitors: "Scan competitors", F_sizing: "Size the market",
  G_verification: "Verify every claim", H_execution: "Build CRM & report",
};
export const STEP_ORDER = ["A_brief", "B_discovery", "C_enrichment", "E_buyers", "D_competitors", "F_sizing", "G_verification", "H_execution"];
export const COMPONENT_LABEL: Record<string, string> = {
  icp_country: "Country match", icp_headcount: "Headcount in range", icp_sector: "Sector match", growth: "Headcount growth",
  hiring: "Hiring signal", need: "Product relevance", buyer: "Buyer availability",
};
export const STATE_LABEL: Record<string, string> = {
  completed: "Completed", completed_with_warnings: "Completed with notes", partial: "Partial", failed: "Could not complete",
};
