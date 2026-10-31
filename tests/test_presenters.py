from marketentry.presenters import breakdown_rows, source_excerpt

from .test_orchestrator import make_handler, mission


def test_breakdown_marks_unknown_components(tmp_path):
    d = mission(tmp_path, make_handler()).run()
    c = next(c for c in d.companies if any(v is None for v in c.score_breakdown.values()))
    rows = breakdown_rows(c)
    assert [r["component"] for r in rows][0] == "icp_country" and sum(r["max"] for r in rows) == 100
    assert any(r["points"] == "unknown" for r in rows) and all(isinstance(r["points"], (int, float, str)) for r in rows)


def test_audit_drill_down_shows_value_in_saved_source(tmp_path):
    d = mission(tmp_path, make_handler()).run()
    ev = next(e for e in d.evidence if e.field_path == "headcount.total" and e.subject_type == "company")
    x = source_excerpt(ev)
    assert x["value_in_source"] and str(x["value_in_source"][0]) == ev.value_observed and x["status"] == "supported"
    assert source_excerpt(ev.model_copy(update={"raw_ref": "/nope.json"}))["value_in_source"] is None
    assert source_excerpt(ev.model_copy(update={"raw_ref": None}))["note"] == "no saved source response"
