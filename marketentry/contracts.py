"""Frozen data contracts. Unknown values are None, never 0 / "" / invented."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["supported", "unsupported", "unverified", "stale", "conflicting"]
Wave = Literal["Wave 1", "Wave 2", "Research Needed"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- brief -----------------------------------------------------------------
class Assumption(_Base):
    field: str
    value: Any = None
    source: Literal["user", "defaulted", "inferred"]
    note: str = ""


class MarketBrief(_Base):
    product_name: str
    product_description: str
    target_country: str
    target_industry: str
    employee_min: int | None = None
    employee_max: int | None = None
    annual_contract_value: float | None = None
    currency: str | None = None
    target_buyer_roles: list[str] = Field(default_factory=list)
    max_target_accounts: int = 20
    max_company_enrichments: int = 10
    max_contacts_per_company: int = 2
    max_buyer_accounts: int = 5
    competitor_keywords: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    unsupported_constraints: list[str] = Field(default_factory=list)
    raw_prompt: str = ""

    @model_validator(mode="after")
    def _range_ok(self) -> "MarketBrief":
        if (
            self.employee_min is not None
            and self.employee_max is not None
            and self.employee_min > self.employee_max
        ):
            raise ValueError("employee_min > employee_max")
        return self


# ---- evidence --------------------------------------------------------------
class Evidence(_Base):
    evidence_id: str
    mission_id: str
    subject_type: Literal["company", "person", "market", "competitor", "calc"]
    subject_id: str
    claim: str
    source_kind: str
    source_record_id: str | None = None
    source_url: str | None = None
    field_path: str | None = None
    raw_ref: str | None = None  # saved raw response file or tool_run id
    value_observed: str | None = None
    retrieved_at_utc: str
    status: Status = "unverified"
    contradiction_with: list[str] = Field(default_factory=list)
    notes: str = ""


# ---- entities --------------------------------------------------------------
class IdentityMatch(_Base):
    method: Literal["company_id", "domain", "name_verified", "unresolved"] = "unresolved"
    confidence: float = 0.0
    decision_note: str = ""


class CompanyRecord(_Base):
    company_id: str | None = None
    name: str
    domain: str | None = None
    linkedin_url: str | None = None
    country: str | None = None
    hq_location: str | None = None
    industry: str | None = None
    industry_tags: list[str] = Field(default_factory=list)
    employee_count: int | None = None
    employee_range: str | None = None
    headcount_growth_6m: float | None = None
    headcount_growth_12m: float | None = None
    open_roles: int | None = None
    funding_total: float | None = None
    last_funding_date: str | None = None
    technologies: list[str] = Field(default_factory=list)
    description: str | None = None
    identity: IdentityMatch = Field(default_factory=IdentityMatch)
    icp_match: bool | None = None
    icp_reasons: list[str] = Field(default_factory=list)
    fit_score: float | None = None
    score_breakdown: dict[str, float | None] = Field(default_factory=dict)
    data_coverage: float = 0.0
    confidence: Literal["high", "medium", "low"] = "low"
    wave: Wave | None = None
    buyer_status: Literal["found", "buyer_not_found", "not_searched"] = "not_searched"
    enriched: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: Status = "unverified"
    flags: list[str] = Field(default_factory=list)


class PersonRecord(_Base):
    person_id: str | None = None
    company_id: str | None = None  # internal FK -> CompanyRecord.company_id
    name: str
    headline: str | None = None
    current_title: str | None = None
    role_matched: str | None = None
    current_employer_name: str | None = None
    current_employer_company_id: str | None = None
    current_employer_domain: str | None = None
    employment_start: str | None = None
    linkedin_url: str | None = None
    employer_verified: bool = False
    verification_method: Literal["id", "domain", "history", "none"] = "none"
    enriched: bool = False
    missing_flags: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: Status = "unverified"


class CompetitorRecord(_Base):
    company_id: str | None = None
    name: str
    domain: str | None = None
    classification: Literal["confirmed", "possible", "insufficient_evidence"] = "insufficient_evidence"
    positioning_claim: str | None = None
    source_url: str | None = None
    employee_count: int | None = None
    headcount_growth_6m: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    identity: IdentityMatch = Field(default_factory=IdentityMatch)


# ---- execution log ---------------------------------------------------------
class ToolRun(_Base):
    run_id: str
    mission_id: str
    tool_name: str
    endpoint: str
    request_hash: str
    request_summary: str = ""  # filters/body only; never headers or keys
    result_status: Literal["ok", "empty", "error", "cached", "replayed", "simulated_failure"]
    http_status: int | None = None
    attempt: int = 1
    duration_ms: int = 0
    credit_cost: float | None = None
    credit_source: Literal["response", "unknown"] = "unknown"
    result_count: int | None = None
    total_count: int | None = None
    error_type: str | None = None
    raw_path: str | None = None
    started_at_utc: str


class StepStatus(_Base):
    name: str
    status: Literal["pending", "running", "done", "warning", "failed", "skipped"] = "pending"
    retries: int = 0
    started: str | None = None
    finished: str | None = None
    warning: str | None = None


class UniverseSummary(_Base):
    total_count: int | None = None
    fetched: int = 0
    filters_applied: Any = None
    post_filters: list[str] = Field(default_factory=list)
    coverage_note: str = ""
    retrieved_at: str | None = None


class SizingResult(_Base):
    observed_count: int | None = None
    acv: float | None = None
    currency: str | None = None
    pool: float | None = None
    pipeline_pool: float | None = None
    formula_text: str = ""
    caveats: list[str] = Field(default_factory=list)


class MissionResult(_Base):
    mission_id: str
    state: Literal["completed", "completed_with_warnings", "failed", "partial"]
    brief: MarketBrief | None = None
    steps: list[StepStatus] = Field(default_factory=list)
    universe: UniverseSummary = Field(default_factory=UniverseSummary)
    sizing: SizingResult = Field(default_factory=SizingResult)
    company_records: int = 0
    buyer_records: int = 0
    competitor_records: int = 0
    verified_claim_fraction: float | None = None
    evidence_total: int = 0
    credit_used: float | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    crm_db_path: str | None = None
    crm_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
