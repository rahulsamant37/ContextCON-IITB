import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from marketentry.api import create_app
from marketentry.config import Settings
from marketentry.crustdata_client import CrustdataClient
from marketentry.jobs import clamp_caps

from .conftest import FIX
from .test_orchestrator import PROMPT, make_handler

KEY = "test-key-SECRET-xyz"


def build(tmp_path, handler=None, **kw):
    s = Settings(_env_file=None, crustdata_api_key=KEY, out_dir=tmp_path, fixtures_dir=FIX, min_interval_s=0,
                 backoff_base_s=0.01, backoff_max_s=0.02, llm_disabled=True, **kw)
    h = handler or make_handler()
    app = create_app(s, client_factory=lambda st: CrustdataClient("tmp", st, transport=httpx.MockTransport(h), sleep=lambda x: None))
    c = TestClient(app)
    assert c.get("/api/auth/me").json()["user"]["guest"] is True  # first visit creates the guest account
    return c, s


def wait_done(c, mid, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        st = c.get(f"/api/missions/{mid}/status").json()
        if st["status"] in ("done", "failed"):
            return st
        time.sleep(0.05)
    raise AssertionError("mission did not finish")


@pytest.fixture
def run(tmp_path):
    c, s = build(tmp_path)
    r = c.post("/api/missions", json={"prompt": PROMPT})
    assert r.status_code == 202
    mid = r.json()["mission_id"]
    assert wait_done(c, mid)["status"] == "done"
    return c, mid, s


def test_health_and_settings_never_expose_keys(tmp_path):
    c, _ = build(tmp_path)
    assert c.get("/api/health").json() == {"ok": True}
    r = c.get("/api/settings")
    assert r.json()["crustdata_key_set"] is True and KEY not in r.text and r.json()["estimate"]["cap"] > 0


def test_preview_parses_without_cost_and_validates_input(tmp_path):
    c, _ = build(tmp_path)
    r = c.post("/api/briefs/preview", json={"prompt": PROMPT}).json()
    assert r["ready"] and r["brief"]["target_country"] == "United Kingdom" and r["brief"]["annual_contract_value"] == 12000
    assert r["mission_id"].startswith("mission_") and r["estimate"]["typical"] > 0
    bad = c.post("/api/briefs/preview", json={"prompt": "Help me sell stuff somewhere nice."}).json()
    assert bad["ready"] is False
    assert c.post("/api/briefs/preview", json={"prompt": "short"}).status_code == 422
    assert c.post("/api/briefs/preview", json={"prompt": "x" * 5000}).status_code == 422


def test_mission_lifecycle_and_core_payload(run):
    c, mid, _ = run
    d = c.get(f"/api/missions/{mid}").json()
    assert d["state"] == "completed_with_warnings" and len(d["accounts"]) == 3 and d["sizing"]["pool"] == 2410 * 12000
    assert "evidence" not in d and "tool_runs" not in d  # heavy lists have their own endpoints
    assert d["recommendation"]["verdict"] and d["waves"] and d["verified_claim_fraction"] == 1.0
    assert KEY not in c.get(f"/api/missions/{mid}?include=full").text
    full = c.get(f"/api/missions/{mid}?include=full").json()
    assert len(full["evidence"]) > 0 and len(full["tool_runs"]) >= 5
    hist = c.get("/api/missions").json()
    assert [m["mission_id"] for m in hist["missions"]] == [mid] and hist["running"] == []


def test_sse_replays_ordered_events_then_ends(run):
    c, mid, _ = run
    import json
    seen = []
    with c.stream("GET", f"/api/missions/{mid}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                seen.append(json.loads(line[6:]))
    assert seen[-1]["type"] == "end"
    steps = [e["step"] for e in seen if e.get("type") == "event" and e.get("msg") == "started"]
    assert steps[:3] == ["A_brief", "B_discovery", "C_enrichment"]
    assert any(e.get("step") == "tool" and e.get("credit") is not None for e in seen)
    seqs = [e["seq"] for e in seen if "seq" in e]
    assert seqs == sorted(seqs)
    # a reconnecting client can resume from an offset
    with c.stream("GET", f"/api/missions/{mid}/events?start=5") as r:
        resumed = [json.loads(l[6:]) for l in r.iter_lines() if l.startswith("data: ")]
    assert resumed[0]["seq"] == 5


def test_account_detail_and_evidence_endpoints(run):
    c, mid, _ = run
    acc = c.get(f"/api/missions/{mid}/accounts/6507").json()
    assert acc["account"]["name"] == "Auquan" and acc["breakdown"][0]["component"] == "icp_country"
    assert acc["evidence"] and all(e["subject_id"] == "6507" for e in acc["evidence"]) and acc["people"]
    assert c.get(f"/api/missions/{mid}/accounts/nope").status_code == 404
    ev = c.get(f"/api/missions/{mid}/evidence", params={"subject": "6507", "q": "headcount"}).json()
    assert ev["total"] >= 1 and all("headcount" in e["claim"].lower() or "headcount" in (e["field_path"] or "") for e in ev["items"])
    eid = next(e["evidence_id"] for e in ev["items"] if e["field_path"] == "headcount.total")
    src = c.get(f"/api/missions/{mid}/evidence/{eid}/source").json()
    assert src["status"] == "supported" and src["value_in_source"]
    assert c.get(f"/api/missions/{mid}/evidence/ev_9999/source").status_code == 404


def test_evidence_source_refuses_files_outside_recorded_dirs(run, tmp_path):
    c, mid, s = run
    import json
    p = tmp_path / mid / "mission.json"
    data = json.loads(p.read_text())
    data["evidence"][0]["raw_ref"] = "/etc/passwd"
    p.write_text(json.dumps(data))
    assert c.get(f"/api/missions/{mid}/evidence/{data['evidence'][0]['evidence_id']}/source").status_code == 403


def test_artifacts_allow_list_and_traversal(run):
    c, mid, _ = run
    pdf = c.get(f"/api/missions/{mid}/artifacts/Market_Entry_Report.pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    assert c.get(f"/api/missions/{mid}/artifacts/Target_Accounts.csv").text.startswith("rank,company_name")
    for bad in ("marketentry.db", "mission.json", "..%2Fmarketentry.db", "events.json", "nope.txt"):
        assert c.get(f"/api/missions/{mid}/artifacts/{bad}").status_code == 404, bad
    assert c.get("/api/missions/..%2F..%2Fetc/status").status_code == 404
    assert c.get("/api/missions/mission_zzzzzzzzzz").status_code == 404


def test_crm_board_edits_persist_and_validate(run):
    c, mid, _ = run
    crm = c.get(f"/api/missions/{mid}/crm").json()
    assert len(crm["companies"]) == 3 and "Won" in crm["stages"] and crm["counts"]["unsent_drafts"] == 2
    row = crm["companies"][0]["id"]
    assert c.patch(f"/api/missions/{mid}/crm/companies/{row}", json={"stage": "Contacted"}).status_code == 200
    assert c.patch(f"/api/missions/{mid}/crm/companies/{row}", json={"stage": "Sent!"}).status_code == 422
    assert c.patch(f"/api/missions/{mid}/crm/companies/99999", json={"stage": "Won"}).status_code == 404
    again = c.get(f"/api/missions/{mid}/crm").json()
    assert next(x for x in again["companies"] if x["id"] == row)["stage"] == "Contacted"
    draft = next(t for t in crm["tasks"] if t["task_type"] == "outreach_draft")
    r = c.patch(f"/api/missions/{mid}/crm/tasks/{draft['id']}", json={"draft_text": "Edited by a human [DRAFT — UNSENT.]"})
    assert r.status_code == 200
    assert c.patch(f"/api/missions/{mid}/crm/tasks/{draft['id']}", json={"status": "sent"}).status_code == 422  # no send state exists
    other = next(t for t in crm["tasks"] if t["task_type"] != "outreach_draft")
    assert c.patch(f"/api/missions/{mid}/crm/tasks/{other['id']}", json={"draft_text": "x"}).status_code == 422
    after = c.get(f"/api/missions/{mid}/crm").json()
    assert next(t for t in after["tasks"] if t["id"] == draft["id"])["draft_text"].startswith("Edited by a human")


def test_duplicate_submission_attaches_to_running_job(tmp_path):
    gate = threading.Event()
    base = make_handler()

    def slow(req):
        if req.url.path == "/company/search":
            gate.wait(10)
        return base(req)
    c, _ = build(tmp_path, slow)
    a = c.post("/api/missions", json={"prompt": PROMPT}).json()
    b = c.post("/api/missions", json={"prompt": PROMPT}).json()
    assert a["mission_id"] == b["mission_id"]
    assert c.get(f"/api/missions/{a['mission_id']}").status_code == 409  # still running
    assert c.get("/api/missions").json()["running"][0]["mission_id"] == a["mission_id"]
    gate.set()
    assert wait_done(c, a["mission_id"])["status"] == "done"
    assert c.get(f"/api/missions/{a['mission_id']}").status_code == 200


def test_unrecognised_prompt_yields_failed_mission_not_a_crash(tmp_path):
    c, _ = build(tmp_path)
    mid = c.post("/api/missions", json={"prompt": "Help me sell stuff somewhere nice."}).json()["mission_id"]
    st = wait_done(c, mid)
    assert st["status"] == "done" and st["state"] == "failed"
    d = c.get(f"/api/missions/{mid}").json()
    assert d["state"] == "failed" and d["accounts"] == [] and d["warnings"]


def test_missing_key_is_a_clear_400_unless_replay(tmp_path):
    s = Settings(_env_file=None, crustdata_api_key=None, out_dir=tmp_path, llm_disabled=True)
    c = TestClient(create_app(s))
    r = c.post("/api/missions", json={"prompt": PROMPT})
    assert r.status_code == 400 and "CRUSTDATA_API_KEY" in r.json()["detail"]


def test_caps_are_clamped_and_unknown_caps_ignored():
    assert clamp_caps({"max_credits_per_mission": 1e9, "max_company_enrichments": 0, "evil": 5, "max_buyer_searches": True}) == {
        "max_credits_per_mission": 1000.0, "max_company_enrichments": 1}


def test_options_for_guided_form(tmp_path):
    c, _ = build(tmp_path)
    o = c.get("/api/options").json()
    assert "Germany" in o["countries"] and "United Kingdom" in o["countries"] and "EUR" in o["currencies"]
    assert "Logistics" in o["sectors"] and "CTO" in o["roles"] and o["size_presets"][0] == [1, 50]


def test_structured_overrides_set_exact_values(tmp_path):
    c, _ = build(tmp_path)
    r = c.post("/api/missions", json={"prompt": "We sell compliance tooling to FinTech companies. Evaluate entry into United Kingdom.",
                                      "overrides": {"employee_min": 50, "employee_max": 500, "annual_contract_value": 12000,
                                                    "currency": "GBP", "target_buyer_roles": ["CEO", "CTO"],
                                                    "product_name": "ComplianceCloud"}})
    mid = r.json()["mission_id"]
    assert wait_done(c, mid)["status"] == "done"
    b = c.get(f"/api/missions/{mid}").json()["brief"]
    assert (b["employee_min"], b["employee_max"], b["annual_contract_value"], b["currency"]) == (50, 500, 12000, "GBP")
    assert b["product_name"] == "ComplianceCloud" and b["target_buyer_roles"] == ["CEO", "CTO"]


# ---- guest accounts ---------------------------------------------------------------------------------
def test_first_visit_creates_a_private_guest_session(tmp_path):
    s = Settings(_env_file=None, crustdata_api_key=KEY, out_dir=tmp_path, llm_disabled=True)
    c = TestClient(create_app(s))
    r = c.get("/api/auth/me")
    cookie = r.headers["set-cookie"].lower()
    assert r.json()["user"]["guest"] is True and r.json()["user"]["name"] == "Guest" and "email" not in r.json()["user"]
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=31536000" in cookie
    again = c.get("/api/auth/me")
    assert again.json()["user"]["id"] == r.json()["user"]["id"] and "set-cookie" not in again.headers  # same guest, no new session
    import sqlite3
    assert sqlite3.connect(tmp_path / "app.db").execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_no_sign_in_endpoints_exist(tmp_path):
    c, _ = build(tmp_path)
    for path in ("/api/auth/signup", "/api/auth/login", "/api/auth/logout"):
        assert c.post(path, json={}).status_code in (404, 405), path


def test_guest_sessions_are_server_side_and_invalid_cookies_get_a_fresh_guest(tmp_path):
    c, _ = build(tmp_path)
    first = c.get("/api/auth/me").json()["user"]["id"]
    forged = TestClient(c.app, cookies={"me_session": "forged-token"})
    assert forged.get("/api/auth/me").json()["user"]["id"] != first  # a forged token never maps to an existing account


def test_guests_cannot_see_each_others_research(tmp_path):
    c, s = build(tmp_path)
    mid = c.post("/api/missions", json={"prompt": PROMPT}).json()["mission_id"]
    assert wait_done(c, mid)["status"] == "done"
    other = TestClient(c.app)  # a different browser = a different guest
    assert other.get("/api/missions").json()["missions"] == []
    for path in (f"/api/missions/{mid}", f"/api/missions/{mid}/crm", f"/api/missions/{mid}/status",
                 f"/api/missions/{mid}/artifacts/Market_Entry_Report.pdf", f"/api/missions/{mid}/events"):
        assert other.get(path).status_code == 404, path
    assert other.patch(f"/api/missions/{mid}/crm/companies/1", json={"stage": "Won"}).status_code == 404
    mid2 = other.post("/api/missions", json={"prompt": PROMPT}).json()["mission_id"]
    assert mid2 != mid  # the same brief from another guest is a separate research
