import json

import httpx

from marketentry.config import Settings
from marketentry.contracts import MarketBrief
from marketentry.crm import CRM
from marketentry.crustdata_client import CrustdataClient
from marketentry.llm import LLMClient
from marketentry.orchestrator import (Mission, build_company_filters, dedupe, pick_categories, run_mission)
from marketentry.normalizers import normalize_company

from .conftest import FIX, fixture

PROMPT = ("We sell security compliance software to fintech companies. Evaluate entry into the UK market, "
          "50-500 employees, £12,000 ACV, buyers: CEO / CTO.")


def make_handler(enrich_status=200, search_body=None, categories=("FinTech",), log=None):
    search = search_body or {**fixture("company_search_uk_fin")["body"], "next_cursor": None}
    enrich = fixture("company_enrich_auquan")["body"]

    def h(req):
        body = json.loads(req.content) if req.content else None
        if log is not None:
            log.append((req.url.path, body))
        if req.url.path.endswith("/autocomplete"):
            return httpx.Response(200, json={"suggestions": [{"value": c} for c in categories]})
        if req.url.path == "/company/search" and body and "search" in body and "filters" not in body:
            return httpx.Response(200, json=fixture("cs_ranked_competitors")["body"], headers={"x-credits-used": "1.15"})
        if req.url.path == "/person/search":  # same people returned for every domain: only Auquan may accept them
            return httpx.Response(200, json=fixture("person_search_auquan_any")["body"], headers={"x-credits-used": "0.69"})
        if req.url.path == "/web/search/live":
            return httpx.Response(200, json=fixture("web_search_competitors")["body"], headers={"x-credits-used": "1"})
        if req.url.path == "/company/search":
            return httpx.Response(200, json=search, headers={"x-credits-used": "1.29"})
        if req.url.path == "/company/enrich":
            if enrich_status != 200:
                return httpx.Response(enrich_status, json={"error": {"type": "boom", "message": "x"}})
            return httpx.Response(200, json=enrich, headers={"x-credits-used": "2"})
        return httpx.Response(404, json={"error": {"type": "not_found"}})
    return h


def settings(tmp_path, **kw):
    return Settings(_env_file=None, crustdata_api_key="test-key", out_dir=tmp_path, fixtures_dir=FIX, min_interval_s=0,
                    backoff_base_s=0.01, backoff_max_s=0.02, llm_disabled=True, **kw)


def mission(tmp_path, handler=None, prompt=PROMPT, **kw):
    s = settings(tmp_path)
    client = CrustdataClient("tmp", s, transport=httpx.MockTransport(handler or make_handler()), sleep=lambda x: None)
    return Mission(prompt, settings=s, client=client, llm=LLMClient(s), **kw)


def test_pure_helpers():
    assert pick_categories("FinTech", ["InsurTech", "fintech", "FinTech Lending"]) == ["fintech", "FinTech Lending"]
    assert pick_categories("Health Care", ["Healthcare", "Hospitals"]) == ["Healthcare"]
    assert pick_categories("Nothing", ["FinTech"]) == []
    b = MarketBrief(product_name="p", product_description="d", target_country="Germany", target_industry="x", employee_min=100)
    conds = build_company_filters(b, ["Logistics"])["conditions"]
    assert {"field": "locations.country", "type": "=", "value": "Germany"} in conds
    assert {"field": "headcount.total", "type": "=>", "value": 100} in conds
    assert not any(c["type"] == "=<" for c in conds)  # no max given => no bound sent


def test_dedupe_by_id_then_domain():
    a = normalize_company({"crustdata_company_id": 1, "basic_info": {"name": "A", "primary_domain": "a.com"}})
    b = normalize_company({"crustdata_company_id": 1, "basic_info": {"name": "A2"}})
    c = normalize_company({"crustdata_company_id": 2, "basic_info": {"name": "A3", "primary_domain": "a.com"}})
    out, dropped = dedupe([a, b, c])
    assert [r.company_id for r in out] == ["1"] and dropped == 2


def test_full_flow_offline(tmp_path):
    log = []
    d = mission(tmp_path, make_handler(log=log)).run()
    assert d.mission_id.startswith("mission_") and d.universe.total_count == 2410
    assert d.universe.filters_applied["conditions"][1]["value"] == ["FinTech"]
    assert len(d.companies) == 3 and d.universe.fetched == 3
    auq = next(c for c in d.companies if c.company_id == "6507")
    assert auq.enriched and auq.open_roles is not None and auq.identity.method == "company_id"
    sent = [p for p, _ in log]
    filtered = [b for p, b in log if p == "/company/search" and "filters" in b]
    assert sent.count("/company/enrich") == 1 and len(filtered) == 2  # 1-row count call + ranked pool
    assert filtered[0]["limit"] == 1 and "search" not in filtered[0]
    assert filtered[1]["search"] == {"query": "FinTech companies", "mode": "hybrid"} and "sorts" not in filtered[1]
    enrich_body = next(b for p, b in log if p == "/company/enrich")
    assert enrich_body["crustdata_company_ids"] and "technographics" not in enrich_body["fields"]
    assert d.sizing.pool == 2410 * 12000 and "2,410 indexed companies × GBP 12,000" in d.sizing.formula_text
    assert d.credit_used == round(1.29 * 2 + 2 + 3 * 0.69 + 1.15 + 1, 2)  # count+pool, enrich, 3 buyer searches, competitors, web
    assert d.crm_counts["companies"] == 3 and d.crm_counts["evidence"] == len(d.evidence) > 0
    assert d.crm_counts["tool_runs"] == len(d.tool_runs) >= 8
    mk = next(e for e in d.evidence if e.subject_type == "market")
    assert mk.status == "supported" and mk.value_observed == "2410" and mk.raw_ref and "company_search" in mk.raw_ref
    assert d.verification.counts.get("unsupported", 0) == 0 and d.verified_claim_fraction == 1.0
    assert d.state == "completed_with_warnings"  # buyer_not_found warnings
    # buyers: Auquan accepts the fixture people (employer id match); Bits/Synapse must reject them
    assert auq.buyer_status == "found" and {c.buyer_status for c in d.companies if c.company_id != "6507"} == {"buyer_not_found"}
    names = [(p.name, p.role_matched) for p in d.people["6507"]]
    assert names == [("Chandini Jain", "CEO"), ("Shub Jain", "CTO")]  # duplicate Chandini profile merged
    assert any(f.startswith("duplicate_profiles_merged") for f in d.people["6507"][0].missing_flags)
    assert "6507" in d.people and set(d.people) == {"6507"}
    assert all(p.employer_verified and p.verification_status == "supported" for p in d.people["6507"])
    assert d.crm_counts["people"] == 2 and d.crm_counts["unsent_drafts"] == 2
    # competitors came from canonical company records, classified conservatively
    assert d.competitors and all(c.company_id for c in d.competitors)
    assert {c.classification for c in d.competitors} <= {"confirmed", "possible", "insufficient_evidence"}
    r = d.result()
    assert r.company_records == 3 and r.mission_id == d.mission_id


def test_rerun_is_idempotent_in_crm(tmp_path):
    first = mission(tmp_path).run()
    second = mission(tmp_path).run()
    assert first.mission_id == second.mission_id
    assert first.crm_counts == second.crm_counts
    crm = CRM(tmp_path / "marketentry.db")
    assert crm.db.execute("SELECT COUNT(*) FROM missions").fetchone()[0] == 1
    crm.close()


def test_enrich_failure_preserves_search_results_with_warning(tmp_path):
    d = mission(tmp_path, make_handler(enrich_status=400)).run()
    assert len(d.companies) == 3 and not any(c.enriched for c in d.companies)
    assert any("enrichment failed" in w for w in d.warnings)
    assert next(s for s in d.steps if s.name == "C_enrichment").status == "warning"
    assert d.crm_counts["companies"] == 3  # still persisted


def test_empty_universe_is_honest(tmp_path):
    d = mission(tmp_path, make_handler(search_body={"companies": [], "total_count": 0, "next_cursor": None})).run()
    assert d.companies == [] and d.state == "failed" and any("empty universe" in w for w in d.warnings)
    assert d.crm_counts == {}  # nothing fabricated, nothing written


def test_unmappable_sector_stops_without_guessing(tmp_path):
    d = mission(tmp_path, make_handler(categories=())).run()
    assert d.state == "failed" and any("no Crustdata category" in w for w in d.warnings) and d.companies == []


def test_unrecognised_prompt_fails_before_any_network(tmp_path):
    log = []
    d = mission(tmp_path, make_handler(log=log), prompt="Help me sell stuff somewhere nice.").run()
    assert d.state == "failed" and log == [] and d.steps[0].status == "failed"


def test_search_page_failure_keeps_partial_results(tmp_path):
    page1 = {**fixture("company_search_uk_fin")["body"], "next_cursor": "c2"}
    n = {"i": 0}
    base = make_handler(search_body=page1)

    def h(req):
        if req.url.path == "/company/search":
            n["i"] += 1
            if n["i"] > 2:  # call 1 = count query, call 2 = first pool page, call 3 = second page (fails)
                return httpx.Response(400, json={"error": {"type": "bad_cursor", "message": "expired"}})
        return base(req)
    d = mission(tmp_path, h).run()
    assert len(d.companies) == 3 and any("page failed" in w for w in d.warnings)
    assert next(s for s in d.steps if s.name == "B_discovery").status == "warning"


def test_country_mismatch_records_are_dropped_and_disclosed(tmp_path):
    body = fixture("company_search_uk_fin")["body"]
    body = {**body, "next_cursor": None, "companies": [
        *body["companies"], {"crustdata_company_id": 99, "basic_info": {"name": "Foreign"}, "locations": {"country": "DEU"},
                             "headcount": {"total": 100}}]}
    d = mission(tmp_path, make_handler(search_body=body)).run()
    assert all(c.name != "Foreign" for c in d.companies)
    assert any("country != United Kingdom" in p for p in d.universe.post_filters)


def test_replay_mode_without_key_degrades_to_honest_failure(tmp_path):
    s = Settings(_env_file=None, crustdata_api_key=None, out_dir=tmp_path, fixtures_dir=tmp_path / "empty", replay=True,
                 llm_disabled=True, min_interval_s=0)
    d = run_mission(PROMPT, settings=s)
    assert d.state == "failed" and d.companies == [] and d.warnings
