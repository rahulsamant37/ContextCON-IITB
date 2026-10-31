export type Source = "user" | "inferred" | "defaulted";
export interface Assumption { field: string; value: unknown; source: Source; note: string }
export interface Brief {
  product_name: string; product_description: string; target_country: string; target_industry: string;
  employee_min: number | null; employee_max: number | null; annual_contract_value: number | null; currency: string | null;
  target_buyer_roles: string[]; competitor_keywords: string[]; max_target_accounts: number;
  assumptions: Assumption[]; unsupported_constraints: string[]; raw_prompt: string;
}
export interface Step { name: string; status: "pending" | "running" | "done" | "warning" | "failed" | "skipped"; warning: string | null; started: string | null; finished: string | null }
export type Wave = "Wave 1" | "Wave 2" | "Research Needed";
export type EvStatus = "supported" | "unsupported" | "unverified" | "stale" | "conflicting";
export interface Account {
  rank: number; company_id: string | null; name: string; domain: string | null; country: string | null;
  employee_count: number | null; employee_range: string | null; headcount_growth_6m: number | null; open_roles: number | null;
  funding_total: number | null; description: string | null; fit_score: number | null; data_coverage: number;
  confidence: "high" | "medium" | "low"; wave: Wave | null; buyer_status: "found" | "buyer_not_found" | "not_searched";
  score_breakdown: Record<string, number | null>; icp_reasons: string[]; flags: string[]; evidence_ids: string[];
  verification_status: EvStatus; enriched: boolean; identity: { method: string; confidence: number; decision_note: string };
}
export interface Person {
  person_id: string | null; company_id: string | null; name: string; headline: string | null; current_title: string | null;
  role_matched: string | null; employer_verified: boolean; verification_method: string; missing_flags: string[];
  verification_status: EvStatus; evidence_ids: string[];
}
export interface Competitor {
  company_id: string | null; name: string; domain: string | null; classification: "confirmed" | "possible" | "insufficient_evidence";
  positioning_claim: string | null; source_url: string | null; employee_count: number | null; evidence_ids: string[];
}
export interface Evidence {
  evidence_id: string; subject_type: string; subject_id: string; claim: string; source_kind: string; field_path: string | null;
  retrieved_at_utc: string; status: EvStatus; value_observed: string | null; notes: string; contradiction_with: string[];
  source_url: string | null;
}
export interface ToolRun {
  run_id: string; tool_name: string; endpoint: string; result_status: string; http_status: number | null; attempt: number;
  duration_ms: number; credit_cost: number | null; result_count: number | null; total_count: number | null; error_type: string | null;
  request_summary: string;
}
export interface Sizing { observed_count: number | null; acv: number | null; currency: string | null; pool: number | null; pipeline_pool: number | null; formula_text: string; caveats: string[] }
export interface Mission {
  mission_id: string; state: "completed" | "completed_with_warnings" | "partial" | "failed"; started_at: string; finished_at: string | null;
  brief: Brief | null; steps: Step[]; universe: { total_count: number | null; fetched: number; filters_applied: unknown; post_filters: string[]; coverage_note: string; retrieved_at: string | null };
  sizing: Sizing; sector_basis: string; recommendation: { verdict: string; text: string }; risks: string[];
  waves: Record<Wave, number>; accounts: Account[]; people: Record<string, Person[]>; competitors: Competitor[];
  llm_runs: { purpose: string; ok: boolean }[]; warnings: string[];
  verification: { counts: Record<string, number>; contradictions: string[]; arithmetic_errors: string[]; checked: number } | null;
  verified_claim_fraction: number | null; credit_used: number | null; artifacts: string[]; crm_counts: Record<string, number>;
  evidence?: Evidence[]; tool_runs?: ToolRun[];
}
export interface Summary {
  mission_id: string; state: Mission["state"]; created_at: string; prompt: string; country: string | null; industry: string | null;
  product: string | null; accounts: number; wave1: number; indexed_count: number | null; credits: number | null;
  verified_fraction: number | null; currency: string | null; pool: number | null;
}
export interface Preview { brief: Brief; mission_id: string; ready: boolean; llm_used: boolean; estimate: { typical: number; cap: number } }
export interface PublicSettings {
  crustdata_key_set: boolean; llm_key_set: boolean; llm_model: string; replay_default: boolean;
  caps: Record<string, number>; estimate: { typical: number; cap: number };
}
export interface RunEvent { seq: number; type: "event" | "status" | "end"; step?: string; msg?: string; ts?: string; credit?: number | null; total?: number | null; n?: number | null; warning?: string | null; status?: string; state?: string; error?: string; http?: number | null }
export interface CrmCompany { id: number; account_key: string; crustdata_company_id: string | null; name: string; domain: string | null; segment: Wave | null; stage: string; fit_score: number | null; coverage_score: number | null; verification_status: EvStatus }
export interface CrmTask { id: number; company_id: number | null; task_type: string; title: string; status: string; draft_text: string | null }
export interface Crm { companies: CrmCompany[]; tasks: CrmTask[]; people: { id: number; company_id: number; name: string; title: string | null }[]; stages: string[]; task_statuses: string[]; counts: Record<string, number> }
export interface AccountDetail { account: Account; breakdown: { component: string; max: number; points: number | string }[]; evidence: Evidence[]; people: Person[] }
export interface SourceExcerpt { evidence_id: string; claim: string; status: EvStatus; notes: string; field_path: string | null; retrieved_at_utc: string; raw_file: string | null; claimed_value: string | null; value_in_source: unknown[] | null; note?: string }
