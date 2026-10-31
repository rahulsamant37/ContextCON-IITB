"""One orchestrator, explicit steps, no agent chatter. Each step records status; a failing step downgrades the
mission to partial/warnings but never discards results already gathered."""
from __future__ import annotations

import re
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable

from .brief_parser import parse_brief
from .buyers import map_buyers
from .competitors import find_competitors
from .config import Settings, get_settings
from .contracts import (Assumption, CompanyRecord, CompetitorRecord, Evidence, MarketBrief, MissionResult, PersonRecord,
                        SizingResult, StepStatus, ToolRun, UniverseSummary)
from .crm import CRM, account_key, mission_id_for
from .crustdata_client import ConfigError, CrustdataClient
from .drafts import plan_tasks
from .evidence import EvidenceLedger, utcnow
from .llm import LLMClient
from .normalizers import (country_matches, merge_company, normalize_company, resolve_identify_entry, unwrap_envelope)
from .scoring import score_and_rank
from .sizing import compute_sizing
from .verifier import VerificationReport, verify_mission

STEPS = ["A_brief", "B_discovery", "C_enrichment", "E_buyers", "D_competitors", "F_sizing", "G_verification", "H_execution"]
SEARCH_FIELDS = ["basic_info", "locations", "headcount"]
ENRICH_FIELDS = ["basic_info", "headcount", "funding", "hiring"]
SEARCH_SORT = [{"field": "headcount.growth_percent.6m", "order": "desc"}]


@dataclass
class MissionData:
    mission_id: str = ""
    brief: MarketBrief | None = None
    companies: list[CompanyRecord] = field(default_factory=list)
    people: dict[str, list[PersonRecord]] = field(default_factory=dict)  # keyed by company_id
    competitors: list[CompetitorRecord] = field(default_factory=list)
    ledger: EvidenceLedger | None = None
    tool_runs: list[ToolRun] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    llm_runs: list[dict] = field(default_factory=list)
    steps: list[StepStatus] = field(default_factory=lambda: [StepStatus(name=n) for n in STEPS])
    universe: UniverseSummary = field(default_factory=UniverseSummary)
    sizing: SizingResult = field(default_factory=SizingResult)
    warnings: list[str] = field(default_factory=list)
    verified_claim_fraction: float | None = None
    verification: VerificationReport | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    crm_counts: dict[str, int] = field(default_factory=dict)
    crm_db_path: str | None = None
    credit_used: float | None = None
    state: str = "failed"
    started_at: str = ""
    finished_at: str | None = None

    @property
    def evidence(self) -> list[Evidence]:
        return self.ledger.items if self.ledger else []

    def result(self) -> MissionResult:
        n_people = sum(len(v) for v in self.people.values())
        return MissionResult(
            mission_id=self.mission_id, state=self.state, brief=self.brief, steps=self.steps, universe=self.universe,
            sizing=self.sizing, company_records=len(self.companies), buyer_records=n_people,
            competitor_records=len(self.competitors), verified_claim_fraction=self.verified_claim_fraction,
            evidence_total=len(self.evidence), credit_used=self.credit_used, artifacts=self.artifacts,
            crm_db_path=self.crm_db_path, crm_counts=self.crm_counts, warnings=self.warnings)


# ---- pure helpers (unit-tested) ----------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def pick_categories(industry: str, suggestions: list[str], limit: int = 4) -> list[str]:
    """Choose autocomplete values for the brief's sector: exact (punctuation/space-insensitive) first, then values containing it."""
    want = _norm(industry)
    if not want:
        return []
    exact = [s for s in suggestions if _norm(s) == want]
    contains = [s for s in suggestions if want in _norm(s) and s not in exact]
    return (exact + contains)[:limit]


def build_company_filters(brief: MarketBrief, categories: list[str]) -> dict:
    conds: list[dict] = [{"field": "locations.country", "type": "=", "value": brief.target_country},
                         {"field": "taxonomy.categories", "type": "in", "value": categories}]
    if brief.employee_min is not None:
        conds.append({"field": "headcount.total", "type": "=>", "value": brief.employee_min})
    if brief.employee_max is not None:
        conds.append({"field": "headcount.total", "type": "=<", "value": brief.employee_max})
    return {"op": "and", "conditions": conds}


def dedupe(records: list[CompanyRecord]) -> tuple[list[CompanyRecord], int]:
    """De-duplicate by canonical id, then domain, then normalised name (first occurrence wins)."""
    seen: set[str] = set()
    out, dropped = [], 0
    for r in records:
        keys = {account_key(r)} | ({f"domain:{r.domain.lower()}"} if r.domain else set())
        if keys & seen:
            dropped += 1
            continue
        seen |= keys
        out.append(r)
    return out, dropped


class Mission:
    def __init__(self, prompt: str, *, overrides: dict | None = None, settings: Settings | None = None,
                 client: CrustdataClient | None = None, llm: LLMClient | None = None,
                 on_event: Callable[[dict], None] | None = None, write_crm: bool = True):
        self.prompt, self.overrides = prompt, overrides
        self.s = settings or get_settings()
        self.llm = llm or LLMClient(self.s)
        self._client, self._on_event, self.write_crm = client, on_event, write_crm
        self.d = MissionData(started_at=utcnow())
        self._records: list[CompanyRecord] = []
        self._pages: list[tuple[str | None, str, int]] = []

    # ---- infrastructure ----------------------------------------------------------------------
    def emit(self, step: str, msg: str, **extra) -> None:
        ev = {"ts": utcnow(), "step": step, "msg": msg, **extra}
        self.d.events.append(ev)
        if self._on_event:
            self._on_event(ev)

    def _status(self, name: str) -> StepStatus:
        return next(s for s in self.d.steps if s.name == name)

    @contextmanager
    def step(self, name: str):
        st = self._status(name)
        st.status, st.started = "running", utcnow()
        self.emit(name, "started")
        try:
            yield st
            if st.status == "running":
                st.status = "done"
        except ConfigError as e:
            st.status, st.warning = "failed", str(e)
            self.d.warnings.append(f"{name}: {e}")
        except Exception as e:  # a step bug must never take down gathered results
            st.status, st.warning = "failed", f"{type(e).__name__}: {e}"
            self.d.warnings.append(f"{name} failed: {type(e).__name__}: {e}")
            self.emit(name, "exception", trace=traceback.format_exc(limit=3))
        finally:
            st.finished = utcnow()
            self.emit(name, st.status, warning=st.warning)

    def skip(self, name: str, why: str) -> None:
        st = self._status(name)
        st.status, st.warning = "skipped", why
        self.d.warnings.append(f"{name} skipped: {why}")
        self.emit(name, "skipped", warning=why)

    def _record_source(self, idx: int) -> tuple[str | None, str | None]:
        ref = None
        for p in self._pages:
            if p[2] <= idx:
                ref = p
        return (ref[0], ref[1]) if ref else (None, None)

    # ---- run ---------------------------------------------------------------------------------
    def run(self) -> MissionData:
        d = self.d
        with self.step("A_brief") as st:
            brief = parse_brief(self.prompt, self.llm, self.overrides)
            d.brief, d.mission_id = brief, mission_id_for(brief)
            d.ledger = EvidenceLedger(d.mission_id)
            for u in brief.unsupported_constraints:
                d.warnings.append(f"brief: {u}")
            if brief.target_country == "unknown" or brief.target_industry == "unknown":
                st.status, st.warning = "failed", "country or sector not recognised; cannot search without guessing"
            self.emit("A_brief", f"{brief.target_industry} / {brief.target_country} / "
                                 f"{brief.employee_min}-{brief.employee_max} / ACV {brief.annual_contract_value} {brief.currency}")
        if d.brief is None or self._status("A_brief").status == "failed":
            return self._finish(skip_rest=True)

        try:
            self._client = self._client or CrustdataClient(d.mission_id, self.s, on_run=lambda r: self.emit(
                "tool", f"{r.tool_name} {r.result_status}", credit=r.credit_cost, total=r.total_count, n=r.result_count))
        except Exception as e:
            d.warnings.append(f"client init failed: {e}")
            return self._finish(skip_rest=True)
        client = self._client
        client.mission_id = d.mission_id

        with self.step("B_discovery") as st:
            self._discovery(client, st)
        if not self._records:
            return self._finish(skip_rest=True)

        with self.step("C_enrichment") as st:
            self._enrichment(client, st)

        self._optional_steps(client)

        with self.step("F_sizing"):
            self._sizing()
        with self.step("G_verification") as st:
            self._verify(st)
        return self._finish()

    def _verify(self, st: StepStatus) -> None:
        d, brief = self.d, self.d.brief
        assert brief is not None and d.ledger is not None
        shortlist = d.companies[: brief.max_target_accounts]
        eligible = sum(1 for c in shortlist if c.wave is not None and c.identity.method != "unresolved" and c.icp_match is not False)
        rep = verify_mission(brief, d.ledger, shortlist, d.people, d.sizing, eligible)
        # competitors' own evidence was verified above; roll their status into nothing else (no record-level status field)
        d.verified_claim_fraction = rep.verified_fraction
        d.verification = rep
        d.warnings.extend(rep.warnings())
        if rep.arithmetic_errors or rep.score_mismatches:
            st.status, st.warning = "warning", "numeric recomputation disagreed with stored values"
        self.emit("G_verification", f"{rep.checked} claims checked: {rep.counts}; fraction supported {rep.verified_fraction}")

    def _optional_steps(self, client: CrustdataClient) -> None:
        with self.step("E_buyers") as st:
            self._buyers(client, st)
        with self.step("D_competitors") as st:
            self._competitors(client, st)

    def _buyers(self, client: CrustdataClient, st: StepStatus) -> None:
        d, brief = self.d, self.d.brief
        assert brief is not None and d.ledger is not None
        accounts = [c for c in d.companies if c.icp_match is not False][: brief.max_buyer_accounts]
        people, status, warns = map_buyers(client, accounts, brief, d.ledger, limit=self.s.max_person_results)
        d.people = people
        d.warnings.extend(warns)
        if warns:
            st.status, st.warning = "warning", f"{len(warns)} account(s) without verified buyers or with failed searches"
        updated = []
        for c in d.companies:
            if c.company_id in status:
                c = c.model_copy(update={"buyer_status": status[c.company_id]})
            updated.append(c)
        d.companies = score_and_rank(updated, brief)  # buyer availability is part of the rubric
        self.emit("E_buyers", f"{len(people)}/{len(accounts)} accounts with verified buyers, "
                              f"{sum(len(v) for v in people.values())} contacts")

    def _competitors(self, client: CrustdataClient, st: StepStatus) -> None:
        d, brief = self.d, self.d.brief
        assert brief is not None and d.ledger is not None
        d.competitors, warns = find_competitors(client, brief, d.ledger)
        d.warnings.extend(warns)
        if warns:
            st.status, st.warning = "warning", warns[0]
        self.emit("D_competitors", f"{len(d.competitors)} candidates: " + ", ".join(
            f"{k}={sum(c.classification == k for c in d.competitors)}" for k in ("confirmed", "possible", "insufficient_evidence")))

    # ---- steps -------------------------------------------------------------------------------
    def _discovery(self, client: CrustdataClient, st: StepStatus) -> None:
        d, brief = self.d, self.d.brief
        assert brief is not None
        cats = pick_categories(brief.target_industry, client.autocomplete("taxonomy.categories", brief.target_industry))
        if not cats:
            st.status, st.warning = "failed", f"no Crustdata category matches sector '{brief.target_industry}'"
            d.warnings.append(f"B_discovery: {st.warning}")
            return
        d.brief = brief = brief.model_copy(update={"assumptions": brief.assumptions + [Assumption(
            field="taxonomy.categories", value=cats, source="inferred",
            note="sector mapped to Crustdata categories via free autocomplete")]})
        filters = build_company_filters(brief, cats)
        self.emit("B_discovery", f"searching with categories {cats}")
        raw, total, warn = client.company_search_paged(filters, SEARCH_FIELDS, self.s.max_company_search_results, SEARCH_SORT)
        self._pages = list(client.search_pages)
        if warn:
            st.status, st.warning = "warning", warn
            d.warnings.append(f"B_discovery: {warn}")
        recs, post, drop_cty = [], [], 0
        for i, item in enumerate(raw):
            ref, ts = self._record_source(i)
            rec = normalize_company(item, ledger=d.ledger, source_kind="crustdata_company_search", raw_ref=ref, retrieved_at=ts)
            if country_matches(brief.target_country, rec.country) is False:
                drop_cty += 1
                continue
            recs.append(rec)
        recs, dup = dedupe(recs)
        if drop_cty:
            post.append(f"dropped {drop_cty} records whose returned country != {brief.target_country}")
        if dup:
            post.append(f"dropped {dup} duplicate records (same id/domain)")
        self._records = recs
        d.universe = UniverseSummary(
            total_count=total, fetched=len(recs), filters_applied=filters, post_filters=post,
            coverage_note=(f"Fetched {len(recs)} of {total if total is not None else 'unknown'} indexed matches, ordered by 6-month "
                           f"headcount growth (desc). Counts are Crustdata-indexed companies, not all businesses in the market."),
            retrieved_at=self._pages[0][1] if self._pages else utcnow())
        d.companies = score_and_rank(recs, brief)
        self.emit("B_discovery", f"{len(recs)} candidates, indexed total {total}")
        if not recs:
            st.status, st.warning = "warning", "search returned no companies"
            d.warnings.append("B_discovery: search returned no companies (empty universe)")

    def _enrichment(self, client: CrustdataClient, st: StepStatus) -> None:
        d, brief = self.d, self.d.brief
        assert brief is not None
        targets = [c for c in d.companies if c.company_id and c.icp_match is not False][: min(brief.max_company_enrichments, self.s.max_company_enrichments)]
        if not targets:
            st.status, st.warning = "warning", "no resolvable candidates to enrich"
            return
        ids = [int(c.company_id) for c in targets if c.company_id and c.company_id.isdigit()]
        r = client.company_enrich(ids=ids, fields=ENRICH_FIELDS)
        if not r.ok:
            st.status, st.warning = "warning", f"enrichment failed ({r.error_type}); continuing with search-only data"
            d.warnings.append(f"C_enrichment: {st.warning}")
            return
        by_id = {c.company_id: c for c in d.companies}
        merged = 0
        for entry in unwrap_envelope(r.body):
            base = by_id.get(str(entry.get("matched_on")))
            enriched, ident = resolve_identify_entry(entry, enriched=True, ledger=d.ledger,
                                                     source_kind="crustdata_company_enrich", raw_ref=r.run.raw_path,
                                                     retrieved_at=r.retrieved_at)
            if base is None or enriched is None or enriched.company_id != base.company_id:
                d.warnings.append(f"C_enrichment: unresolved/ambiguous enrich match for {entry.get('matched_on')}: {ident.decision_note[:120]}")
                continue
            m = merge_company(base, enriched)
            m.identity = ident
            by_id[base.company_id] = m
            merged += 1
        d.companies = score_and_rank(list(by_id.values()), brief)
        self._records = list(by_id.values())
        self.emit("C_enrichment", f"enriched {merged}/{len(targets)} accounts")

    def _sizing(self) -> None:
        d, brief = self.d, self.d.brief
        assert brief is not None
        shortlist = d.companies[: brief.max_target_accounts]
        d.sizing = compute_sizing(brief, d.universe.total_count, shortlist, d.universe.post_filters)
        if d.universe.total_count is not None and d.ledger is not None:
            ref = self._pages[0][0] if self._pages else None
            d.ledger.add(subject_type="market", subject_id=d.mission_id,
                         claim=f"Observed indexed companies matching filters: {d.universe.total_count}",
                         source_kind="crustdata_company_search", field_path="total_count", raw_ref=ref,
                         value_observed=str(d.universe.total_count), status="supported",
                         retrieved_at_utc=d.universe.retrieved_at or utcnow(),
                         notes="indexed count; coverage-limited")
        self.emit("F_sizing", d.sizing.formula_text.replace("\n", " | "))

    def _execute(self) -> None:
        """Step H: persist to the local CRM (idempotent) with unsent drafts."""
        d, brief = self.d, self.d.brief
        assert brief is not None and d.ledger is not None
        crm = CRM(self.s.crm_path)
        try:
            crm.upsert_mission(d.mission_id, brief.raw_prompt, brief, d.state, d.started_at, utcnow(), d.warnings)
            shortlist = d.companies[: brief.max_target_accounts]
            row_ids = {account_key(c): crm.upsert_company(d.mission_id, c) for c in shortlist}
            for c in shortlist:
                for p in d.people.get(c.company_id or account_key(c), []):
                    crm.upsert_person(d.mission_id, p, row_ids[account_key(c)])
            ev = {e.evidence_id: e for e in d.ledger.items}
            for t in plan_tasks(shortlist, d.people, brief, ev, self.llm):
                crm.upsert_task(d.mission_id, t.task_key, row_ids.get(t.account_key), t.task_type, t.title, t.status, t.draft_text)
            crm.replace_evidence(d.mission_id, d.ledger.items)
            crm.replace_tool_runs(d.mission_id, d.tool_runs)
            crm.sync_segments(d.mission_id)
            d.crm_counts, d.crm_db_path = crm.counts(d.mission_id), str(self.s.crm_path)
        finally:
            crm.close()

    def _finish(self, skip_rest: bool = False) -> MissionData:
        d = self.d
        if skip_rest:
            for st in d.steps:
                if st.status == "pending":
                    st.status = "skipped"
        if self._client is not None:
            d.tool_runs = list(self._client.tool_runs)
            d.credit_used = round(self._client.credits_used, 4)
            d.warnings.extend(w for w in self._client.warnings if w not in d.warnings)
        d.llm_runs = list(self.llm.runs)
        d.warnings.extend(f"LLM {r['purpose']} failed ({r.get('error_type')}); rules/template used"
                          for r in d.llm_runs if not r.get("ok"))
        bad_steps = [s for s in d.steps if s.status == "failed"]
        d.state = ("failed" if not d.companies else "partial" if bad_steps else
                   "completed_with_warnings" if d.warnings or any(s.status in ("warning", "skipped") for s in d.steps)
                   else "completed")
        if d.brief is not None and d.ledger is not None and d.companies and self.write_crm:
            with self.step("H_execution") as st:
                d.finished_at = utcnow()
                self._execute()
            if st.status == "failed":
                d.state = "partial"
        else:
            self._status("H_execution").status = "skipped"
        d.finished_at = utcnow()
        return d


def run_mission(prompt: str, **kw) -> MissionData:
    return Mission(prompt, **kw).run()
