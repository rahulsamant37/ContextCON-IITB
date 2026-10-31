from pathlib import Path

from marketentry.ui.helpers import (accounts_rows, breakdown_rows, buyer_rows, competitor_rows, crm_view, evidence_rows,
                                    source_excerpt, tool_run_rows)

from .test_orchestrator import make_handler, mission


def data(tmp_path):
    return mission(tmp_path, make_handler()).run()


def test_tables_shaped_from_real_mission_data(tmp_path):
    d = data(tmp_path)
    acc = accounts_rows(d)
    assert acc and acc[0]["rank"] == 1 and all(r["wave"] and r["verified"] for r in acc)
    assert "unknown" in {str(v) for r in acc for v in r.values()}  # nulls rendered explicitly
    assert {r["tool"] for r in tool_run_rows(d)} >= {"company_search", "company_enrich", "person_search"}
    assert any(r["employer verified"].startswith("yes") for r in buyer_rows(d))
    assert any(r["flags"] == "buyer_not_found" for r in buyer_rows(d))
    assert competitor_rows(d) and breakdown_rows(d.companies[0])[0]["component"] == "icp_country"


def test_audit_drill_down_shows_value_in_saved_source(tmp_path):
    d = data(tmp_path)
    ev = next(e for e in d.evidence if e.field_path == "headcount.total" and e.subject_type == "company")
    x = source_excerpt(ev)
    assert x["value_in_source"] and str(x["value_in_source"][0]) == ev.value_observed and x["status"] == "supported"
    ev2 = ev.model_copy(update={"raw_ref": "/nope.json"})
    assert source_excerpt(ev2)["value_in_source"] is None
    assert evidence_rows(d, ev.subject_id)


def test_crm_view_matches_counts(tmp_path):
    d = data(tmp_path)
    v = crm_view(d.crm_db_path, d.mission_id)
    assert len(v["companies"]) == d.crm_counts["companies"] and len(v["crm_tasks"]) == d.crm_counts["crm_tasks"]
    assert any(t["status"] == "draft_unsent" for t in v["crm_tasks"])


def test_streamlit_app_renders_without_error():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parent.parent / "marketentry" / "ui" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    assert [t.label for t in at.tabs][:4] == ["1 Request", "2 Live execution trace", "3 Market intelligence", "4 Deliverables & CRM"]


def test_run_button_with_empty_replay_fails_honestly_and_still_renders(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("OUT_DIR", str(tmp_path))
    monkeypatch.setenv("FIXTURES_DIR", str(tmp_path / "none"))
    from marketentry import config
    config.get_settings.cache_clear()
    app = Path(__file__).resolve().parent.parent / "marketentry" / "ui" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=60).run()
    at.sidebar.toggle[0].set_value(True)  # REPLAY
    at.run()
    runbtn = next(b for b in at.button if b.label == "Run mission")
    runbtn.click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("failed" in str(m.value) for m in at.metric) or any("failed" in str(m.value) for m in at.sidebar.metric)
    config.get_settings.cache_clear()
