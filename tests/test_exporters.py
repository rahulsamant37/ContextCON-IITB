import csv
import json
from pathlib import Path

from .test_orchestrator import make_handler, mission


def run(tmp_path, **kw):
    return mission(tmp_path, make_handler(**kw)).run()


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_all_deliverables_written(tmp_path):
    d = run(tmp_path)
    for name in ("Target_Accounts.csv", "Buyer_Map.csv", "Competitive_Landscape.csv", "Evidence_Log.json",
                 "Market_Entry_Report.html", "Market_Entry_Report.pdf", "marketentry.db"):
        assert Path(d.artifacts[name]).exists(), name
    assert Path(d.artifacts["Market_Entry_Report.pdf"]).read_bytes()[:5] == b"%PDF-"


def test_target_accounts_csv_is_traceable_and_marks_unknowns(tmp_path):
    d = run(tmp_path)
    r = rows(d.artifacts["Target_Accounts.csv"])
    assert len(r) == 3 and [int(x["rank"]) for x in r] == [1, 2, 3]
    assert len({x["crustdata_company_id"] for x in r}) == 3 and "6507" in {x["crustdata_company_id"] for x in r}
    auq = next(x for x in r if x["crustdata_company_id"] == "6507")
    assert auq["evidence_refs"].startswith("ev_") and auq["identity_method"] == "company_id"
    assert auq["wave"] and auq["buyer_status"] == "found"
    assert all(x["sector_basis"].startswith("matched by search filter") for x in r)
    assert any("unknown" in x["unknown_fields"] or x["unknown_fields"] for x in r)
    assert "unknown" in {x["open_roles"] for x in r} | {x["total_funding_usd"] for x in r}  # nulls never blank/zero


def test_buyer_map_has_verified_people_and_explicit_not_found(tmp_path):
    d = run(tmp_path)
    r = rows(d.artifacts["Buyer_Map.csv"])
    verified = [x for x in r if x["person_name"] != "unknown"]
    assert {x["person_name"] for x in verified} == {"Chandini Jain", "Shub Jain"}
    assert all(x["employer_verified"] == "True" and x["employer_company_id"] == "6507" for x in verified)
    nf = [x for x in r if x["person_name"] == "unknown"]
    assert nf and all("buyer_not_found" in x["missing_data_flags"] for x in nf)
    assert not any("@" in v for x in r for v in x.values())  # no email addresses anywhere


def test_competitive_landscape_never_invents_differentiators(tmp_path):
    d = run(tmp_path)
    r = rows(d.artifacts["Competitive_Landscape.csv"])
    assert r and all(x["differentiators"].startswith("not assessed") for x in r)
    assert all(x["classification"] in ("confirmed", "possible", "insufficient_evidence") for x in r)


def test_evidence_log_complete_and_secret_free(tmp_path):
    d = run(tmp_path)
    log = json.loads(Path(d.artifacts["Evidence_Log.json"]).read_text())
    assert len(log["evidence"]) == len(d.evidence) and log["tool_runs"] and log["sizing"]["pool"] == 2410 * 12000
    for e in log["evidence"]:
        assert e["evidence_id"] and e["retrieved_at_utc"] and e["status"] in {"supported", "unsupported", "unverified", "stale", "conflicting"}
    assert log["verified_claim_fraction"] is not None
    blob = Path(d.artifacts["Evidence_Log.json"]).read_text() + Path(d.artifacts["Market_Entry_Report.html"]).read_text()
    assert "test-key" not in blob


def test_report_states_formula_assumptions_and_caveats(tmp_path):
    html = Path(run(tmp_path).artifacts["Market_Entry_Report.html"]).read_text()
    assert "2,410 indexed companies" in html and "GBP 12,000" in html
    assert "not TAM" in html and "Assumptions" in html and "buyer_not_found" in html
    assert "Wave 1" in html and "Evidence_Log.json" in html


def test_no_acv_report_has_no_money(tmp_path):
    from marketentry.brief_parser import parse_brief  # noqa: F401
    d = mission(tmp_path, make_handler(), prompt=("We sell security compliance software to fintech companies. "
                                                  "Evaluate entry into the UK, 50-500 employees.")).run()
    html = Path(d.artifacts["Market_Entry_Report.html"]).read_text()
    assert d.sizing.pool is None and "No ACV supplied" in html and "GBP" not in html.split("Bottom-up market sizing")[1].split("Buyer map")[0]
