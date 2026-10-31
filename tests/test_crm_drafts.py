import httpx
import pytest

from marketentry.config import Settings
from marketentry.contracts import CompanyRecord, IdentityMatch, MarketBrief, PersonRecord
from marketentry.crm import CRM, account_key, mission_id_for
from marketentry.drafts import FOOTER, plan_tasks, template_draft
from marketentry.evidence import EvidenceLedger
from marketentry.llm import LLMClient
from marketentry.normalizers import normalize_company, normalize_person
from marketentry.scoring import score_and_rank

from .conftest import fixture


def brief(**kw):
    base = dict(product_name="P", product_description="security compliance software", target_country="United Kingdom",
                target_industry="FinTech", employee_min=50, employee_max=500, annual_contract_value=12000.0, currency="GBP")
    return MarketBrief(**{**base, **kw})


def build():
    """Real fixture data: Auquan (enriched) + its CEO, plus Bits from search."""
    ledger = EvidenceLedger("m")
    auq = normalize_company(fixture("company_enrich_auquan")["body"][0]["matches"][0]["company_data"], enriched=True,
                            ledger=ledger, source_kind="crustdata_company_enrich", raw_ref="fixtures/raw/company_enrich_auquan.json")
    bits = normalize_company(fixture("company_search_uk_fin")["body"]["companies"][0], ledger=ledger)
    ceo = normalize_person(fixture("person_search_auquan_any")["body"]["profiles"][0], auq, ["CEO"], ledger=ledger)
    auq.buyer_status = "found"
    return ledger, score_and_rank([auq, bits], brief(employee_min=0, employee_max=1000)), ceo


def save(crm, mid, ledger, comps, ceo):
    crm.upsert_mission(mid, "prompt", brief(), "completed")
    ids = {}
    for c in comps:
        ids[account_key(c)] = crm.upsert_company(mid, c)
    crm.upsert_person(mid, ceo, ids["id:6507"])
    ev = {e.evidence_id: e for e in ledger.items}
    for s in plan_tasks(comps, {"6507": [ceo]}, brief(), ev):
        crm.upsert_task(mid, s.task_key, ids.get(s.account_key), s.task_type, s.title, s.status, s.draft_text)
    crm.replace_evidence(mid, ledger.items)
    crm.sync_segments(mid)


def test_rerun_creates_no_duplicates():
    ledger, comps, ceo = build()
    crm = CRM(":memory:")
    save(crm, "m1", ledger, comps, ceo)
    first = crm.counts("m1")
    save(crm, "m1", ledger, comps, ceo)
    save(crm, "m1", ledger, comps, ceo)
    assert crm.counts("m1") == first
    assert first["companies"] == 2 and first["people"] == 1 and first["evidence"] == len(ledger.items)
    assert first["unsent_drafts"] == 1 and first["segments"] == 3


def test_rerun_preserves_manual_stage_and_task_status():
    ledger, comps, ceo = build()
    crm = CRM(":memory:")
    save(crm, "m1", ledger, comps, ceo)
    crm.db.execute("UPDATE companies SET stage='Contacted' WHERE account_key='id:6507'")
    crm.db.execute("UPDATE crm_tasks SET status='done' WHERE task_type='qualify'")
    crm.db.commit()
    save(crm, "m1", ledger, comps, ceo)
    assert crm.db.execute("SELECT stage FROM companies WHERE account_key='id:6507'").fetchone()[0] == "Contacted"
    assert crm.db.execute("SELECT COUNT(*) FROM crm_tasks WHERE status='done'").fetchone()[0] >= 1


def test_same_company_in_two_missions_is_two_rows_and_mission_id_is_deterministic():
    ledger, comps, ceo = build()
    crm = CRM(":memory:")
    save(crm, "m1", ledger, comps, ceo)
    save(crm, "m2", ledger, comps, ceo)
    assert crm.counts("m1")["companies"] == crm.counts("m2")["companies"] == 2
    assert mission_id_for(brief()) == mission_id_for(brief(raw_prompt="different wording"))
    assert mission_id_for(brief()) != mission_id_for(brief(target_country="Germany"))


def test_account_key_fallbacks():
    assert account_key(CompanyRecord(name="A", company_id="5")) == "id:5"
    assert account_key(CompanyRecord(name="A", domain="a.com")) == "domain:a.com"
    assert account_key(CompanyRecord(name=" A Ltd ")) == "name:a ltd"


def test_evidence_and_tool_runs_replaced_not_appended():
    from marketentry.contracts import ToolRun
    crm = CRM(":memory:")
    run = ToolRun(run_id="run_0001", mission_id="m1", tool_name="company_search", endpoint="POST /company/search",
                  request_hash="h", result_status="ok", started_at_utc="t", credit_cost=0.33)
    for _ in range(3):
        crm.replace_tool_runs("m1", [run])
    assert crm.counts("m1")["tool_runs"] == 1
    assert crm.rows("tool_runs", "m1")[0]["credit_cost"] == 0.33


def test_schema_has_no_email_or_phone_columns():
    crm = CRM(":memory:")
    cols = [r[1] for t in ("people", "companies", "crm_tasks") for r in crm.db.execute(f"PRAGMA table_info({t})")]
    assert not any(k in c for c in cols for k in ("email", "phone"))


# ---- drafts -----------------------------------------------------------------
def test_draft_is_unsent_and_uses_only_evidenced_facts():
    ledger, comps, ceo = build()
    ev = {e.evidence_id: e for e in ledger.items}
    auq = next(c for c in comps if c.company_id == "6507")
    text, used = template_draft(auq, ceo, brief(), ev)
    assert FOOTER in text and text.startswith("Hi Chandini")
    assert f"{auq.employee_count}" in text or "grew" in text
    assert used and all(u in ev for u in used)
    assert "@" not in text and "http" not in text


def test_draft_omits_facts_without_evidence():
    c = CompanyRecord(name="NoEv", company_id="9", headcount_growth_6m=50.0, open_roles=30, employee_count=100,
                      identity=IdentityMatch(method="company_id", confidence=1))
    text, used = template_draft(c, None, brief(), {})
    assert used == [] and "50%" not in text and "30 open" not in text and text.startswith("Hi there")


def test_plan_tasks_by_wave_and_statuses():
    ledger, comps, ceo = build()
    ev = {e.evidence_id: e for e in ledger.items}
    specs = plan_tasks(comps, {"6507": [ceo]}, brief(), ev)
    kinds = {(s.account_key, s.task_type) for s in specs}
    assert ("id:6507", "outreach_draft") in kinds
    assert all(s.status == "draft_unsent" for s in specs if s.task_type == "outreach_draft")
    assert sum(s.task_type == "launch_checklist" for s in specs) == 3
    assert len({s.task_key for s in specs}) == len(specs)


def test_unverified_person_gets_no_draft():
    ledger, comps, ceo = build()
    ceo2 = ceo.model_copy(update={"employer_verified": False})
    specs = plan_tasks(comps, {"6507": [ceo2]}, brief(), {e.evidence_id: e for e in ledger.items})
    assert not any(s.task_type == "outreach_draft" for s in specs)
    assert any(s.task_type == "research" and "Find a verified buyer" in s.title for s in specs)


def _llm(text):
    s = Settings(_env_file=None, llm_api_key="k", llm_base_url="https://x.test/v1")
    return LLMClient(s, transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": text}}]})), sleep=lambda x: None)


def test_llm_polish_rejected_when_it_adds_numbers_or_links():
    ledger, comps, ceo = build()
    ev = {e.evidence_id: e for e in ledger.items}
    base = {s.task_key: s for s in plan_tasks(comps, {"6507": [ceo]}, brief(), ev)}
    key = next(k for k in base if "outreach" in k)
    for bad in (f"Hi! We grew 999% and you can email me. {FOOTER}", f"See https://evil.example {FOOTER}", "no footer"):
        out = {s.task_key: s for s in plan_tasks(comps, {"6507": [ceo]}, brief(), ev, _llm(bad))}
        assert out[key].draft_text == base[key].draft_text  # fell back to template
    good = f"Hi Chandini, a quick note about compliance tooling for Auquan. {FOOTER}"
    out = {s.task_key: s for s in plan_tasks(comps, {"6507": [ceo]}, brief(), ev, _llm(good))}
    assert out[key].draft_text == good


def test_prune_removes_rows_a_rerun_no_longer_produces_but_keeps_manual_progress():
    ledger, comps, ceo = build()
    crm = CRM(":memory:")
    save(crm, "m1", ledger, comps, ceo)
    crm.db.execute("UPDATE companies SET stage='Contacted' WHERE account_key='id:6507'")
    crm.db.commit()
    keep = [account_key(c) for c in comps if c.company_id == "6507"]
    pruned = crm.prune_mission("m1", keep, [], [])
    assert pruned["companies"] == 1 and pruned["people"] == 1 and pruned["crm_tasks"] >= 1
    assert crm.counts("m1")["companies"] == 1
    assert crm.db.execute("SELECT stage FROM companies").fetchone()[0] == "Contacted"
    assert crm.prune_mission("m1", ["nothing"], [], [])["companies"] == 1 and crm.counts("m1")["companies"] == 0


def test_human_edited_draft_survives_a_rerun_but_untouched_drafts_refresh():
    ledger, comps, ceo = build()
    crm = CRM(":memory:")
    save(crm, "m1", ledger, comps, ceo)
    draft = crm.db.execute("SELECT id, draft_text FROM crm_tasks WHERE task_type='outreach_draft'").fetchone()
    assert crm.update_task("m1", draft["id"], draft_text="Edited by a human. [DRAFT — UNSENT.]")
    crm.db.execute("UPDATE crm_tasks SET draft_text='stale generated text' WHERE task_type='outreach_draft' AND id<>?", (draft["id"],))
    crm.db.commit()
    save(crm, "m1", ledger, comps, ceo)  # re-run regenerates drafts
    after = {r["id"]: r["draft_text"] for r in crm.db.execute("SELECT id, draft_text FROM crm_tasks WHERE task_type='outreach_draft'")}
    assert after[draft["id"]] == "Edited by a human. [DRAFT — UNSENT.]"


def test_old_database_without_draft_edited_column_is_migrated(tmp_path):
    import sqlite3
    p = tmp_path / "old.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE crm_tasks(id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, task_key TEXT NOT NULL, company_id INTEGER, "
               "task_type TEXT, title TEXT, status TEXT, draft_text TEXT, UNIQUE(mission_id, task_key))")
    db.commit(); db.close()
    crm = CRM(p)
    assert "draft_edited" in {r[1] for r in crm.db.execute("PRAGMA table_info(crm_tasks)")}
