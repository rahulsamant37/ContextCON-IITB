"""End-to-end replay determinism and the failure behaviours judged in the acceptance tests."""
import shutil

import httpx

from marketentry.config import Settings
from marketentry.crm import CRM
from marketentry.crustdata_client import CrustdataClient
from marketentry.llm import LLMClient
from marketentry.orchestrator import Mission, run_mission

from .test_orchestrator import PROMPT, make_handler, mission


def test_replay_reproduces_a_recorded_live_run_with_zero_network(tmp_path):
    rec_out = tmp_path / "rec"
    live = mission(rec_out, make_handler()).run()
    fx = tmp_path / "fixtures"
    fx.mkdir()
    for f in (rec_out / live.mission_id / "raw").glob("*.json"):
        shutil.copy2(f, fx / f.name)

    s = Settings(_env_file=None, crustdata_api_key=None, replay=True, fixtures_dir=fx, out_dir=tmp_path / "replay",
                 llm_disabled=True, min_interval_s=0)
    again = run_mission(PROMPT, settings=s)
    assert again.mission_id == live.mission_id and again.state == live.state
    assert [c.company_id for c in again.companies] == [c.company_id for c in live.companies]
    assert [c.fit_score for c in again.companies] == [c.fit_score for c in live.companies]
    assert again.universe.total_count == live.universe.total_count == 2410
    assert again.sizing.formula_text == live.sizing.formula_text
    assert {r.result_status for r in again.tool_runs} == {"replayed", "cached"} or {"replayed"} <= {r.result_status for r in again.tool_runs}
    assert again.credit_used == 0 and again.verified_claim_fraction == 1.0
    assert {p.person_id for v in again.people.values() for p in v} == {p.person_id for v in live.people.values() for p in v}


def test_simulated_transient_failure_is_visible_and_run_still_succeeds(tmp_path):
    s = Settings(_env_file=None, crustdata_api_key="k", out_dir=tmp_path, min_interval_s=0, backoff_base_s=0.01,
                 backoff_max_s=0.02, llm_disabled=True, simulate_transient_failure=True)
    client = CrustdataClient("tmp", s, transport=httpx.MockTransport(make_handler()), sleep=lambda x: None)
    d = Mission(PROMPT, settings=s, client=client, llm=LLMClient(s)).run()
    assert len(d.companies) == 3 and d.crm_counts["companies"] == 3
    sim = [r for r in d.tool_runs if r.result_status == "simulated_failure"]
    assert len(sim) == 1 and sim[0].error_type == "simulated_transient_failure"
    assert any("Simulated transient failure" in w for w in d.warnings) and d.state == "completed_with_warnings"


def test_rate_limit_then_recovery_is_logged_and_preserved(tmp_path):
    base = make_handler()
    n = {"i": 0}

    def h(req):
        if req.url.path == "/company/enrich":
            n["i"] += 1
            if n["i"] == 1:
                return httpx.Response(429, json={"error": {"type": "rate_limited", "message": "slow down"}})
        return base(req)
    d = mission(tmp_path, h).run()
    enrich = [r for r in d.tool_runs if r.tool_name == "company_enrich"]
    assert [r.result_status for r in enrich] == ["error", "ok"] and enrich[0].error_type == "rate_limited"
    assert any(c.enriched for c in d.companies)


def test_person_search_outage_marks_buyers_unknown_not_missing(tmp_path):
    base = make_handler()

    def h(req):
        if req.url.path == "/person/search":
            return httpx.Response(500, text="upstream down")
        return base(req)
    d = mission(tmp_path, h).run()
    assert {c.buyer_status for c in d.companies} == {"not_searched"}  # failure is not 'no buyer exists'
    assert d.people == {} and any("person search failed" in w for w in d.warnings)
    assert d.crm_counts["companies"] == 3 and d.state in ("completed_with_warnings", "partial")


def test_ambiguous_enrich_identity_is_rejected_not_merged(tmp_path):
    import json
    from .conftest import fixture
    env = fixture("company_enrich_auquan")["body"]
    bad = json.loads(json.dumps(env))
    bad[0]["matches"].append(json.loads(json.dumps(bad[0]["matches"][0])))  # two equal-confidence candidates
    base = make_handler()

    def h(req):
        if req.url.path == "/company/enrich":
            return httpx.Response(200, json=bad, headers={"x-credits-used": "2"})
        return base(req)
    d = mission(tmp_path, h).run()
    assert not any(c.enriched for c in d.companies)
    assert any("ambiguous" in w for w in d.warnings)


def test_idempotent_crm_across_three_runs_and_key_never_in_outputs(tmp_path):
    ds = [mission(tmp_path, make_handler()).run() for _ in range(3)]
    assert ds[0].crm_counts == ds[1].crm_counts == ds[2].crm_counts
    crm = CRM(tmp_path / "marketentry.db")
    keys = crm.db.execute("SELECT account_key, COUNT(*) c FROM companies GROUP BY mission_id, account_key HAVING c > 1").fetchall()
    assert keys == []
    crm.close()
    for p in tmp_path.rglob("*"):
        if p.is_file() and p.suffix in {".json", ".csv", ".html", ".db"}:
            assert b"test-key" not in p.read_bytes(), p


def test_rerun_with_changed_data_mirrors_latest_result_without_stale_rows(tmp_path):
    from .conftest import fixture
    full = fixture("company_search_uk_fin")["body"]
    first = mission(tmp_path, make_handler(search_body={**full, "next_cursor": None})).run()
    assert first.crm_counts["companies"] == 3
    fewer = {**full, "next_cursor": None, "companies": full["companies"][:2]}
    second = mission(tmp_path, make_handler(search_body=fewer)).run()
    assert second.mission_id == first.mission_id and second.crm_counts["companies"] == 2
    crm = CRM(tmp_path / "marketentry.db")
    assert crm.db.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 2
    assert crm.db.execute("SELECT COUNT(*) FROM crm_tasks t LEFT JOIN companies c ON c.id=t.company_id "
                          "WHERE t.company_id IS NOT NULL AND c.id IS NULL").fetchone()[0] == 0  # no orphan tasks
    crm.close()
