from datetime import datetime, timedelta, timezone

from marketentry.contracts import MarketBrief
from marketentry.evidence import EvidenceLedger
from marketentry.normalizers import normalize_company, normalize_person
from marketentry.scoring import score_and_rank
from marketentry.sizing import compute_sizing
from marketentry.verifier import check_evidence, find_contradictions, rollup, verify_mission

from .conftest import FIX, fixture

SEARCH = str(FIX / "company_search_uk_fin.json")
ENRICH = str(FIX / "company_enrich_auquan.json")
PERSON = str(FIX / "person_search_auquan_any.json")


def brief(**kw):
    base = dict(product_name="P", product_description="compliance software", target_country="United Kingdom",
                target_industry="FinTech", employee_min=0, employee_max=1000, annual_contract_value=12000.0, currency="GBP")
    return MarketBrief(**{**base, **kw})


def build(ts=None):
    ledger = EvidenceLedger("m")
    kw = {"retrieved_at": ts} if ts else {}
    cs = [normalize_company(c, ledger=ledger, raw_ref=SEARCH, **kw) for c in fixture("company_search_uk_fin")["body"]["companies"]]
    enriched = normalize_company(fixture("company_enrich_auquan")["body"][0]["matches"][0]["company_data"], enriched=True, ledger=ledger,
                                 source_kind="crustdata_company_enrich", raw_ref=ENRICH, **kw)
    auq = next(c for c in cs if c.company_id == "6507")
    ceo = normalize_person(fixture("person_search_auquan_any")["body"]["profiles"][0], auq, ["CEO"], ledger=ledger,
                           raw_ref=PERSON, **kw)
    return ledger, cs, enriched, ceo


def fresh_ts():
    return datetime.now(timezone.utc).isoformat()


def test_real_fixture_claims_are_supported_when_fresh():
    ledger, cs, _, ceo = build(fresh_ts())
    cache = {}
    for e in ledger.items:
        st, note = check_evidence(e, cache, 72)
        assert st == "supported", (e.claim, e.field_path, note)
    assert any(e.subject_type == "person" for e in ledger.items)


def test_old_retrieval_is_flagged_stale_not_dropped():
    ledger, *_ = build((datetime.now(timezone.utc) - timedelta(hours=100)).isoformat())
    st, note = check_evidence(ledger.items[0], {}, 72)
    assert st == "stale" and "100h" in note or "h ago" in note


def test_tampered_value_is_unsupported():
    ledger, *_ = build(fresh_ts())
    ev = next(e for e in ledger.items if e.field_path == "headcount.total")
    ev.value_observed = "99999"
    st, note = check_evidence(ev, {}, 72)
    assert st == "unsupported" and "99999" in note


def test_wrong_identity_record_is_unsupported():
    ledger, *_ = build(fresh_ts())
    ev = next(e for e in ledger.items if e.field_path == "headcount.total")
    ev.source_record_id = "424242"  # id not in the cited response
    assert check_evidence(ev, {}, 72)[0] == "unsupported"


def test_missing_source_is_unverified_not_supported():
    ledger, *_ = build(fresh_ts())
    ev = ledger.items[0]
    ev.raw_ref = "/nonexistent/file.json"
    assert check_evidence(ev, {}, 72)[0] == "unverified"
    ev.raw_ref = None
    assert check_evidence(ev, {}, 72)[0] == "unverified"


def test_absent_field_claim_is_unsupported():
    ledger, *_ = build(fresh_ts())
    ev = next(e for e in ledger.items if e.field_path == "headcount.total").model_copy(update={"field_path": "hiring.openings_count"})
    assert check_evidence(ev, {}, 72)[0] == "unsupported"


def test_contradiction_between_search_and_enrich_is_detected():
    ledger, cs, enriched, _ = build(fresh_ts())
    auq_search = next(c for c in cs if c.company_id == "6507")
    if auq_search.employee_count == enriched.employee_count:  # force a conflict if the live data happened to agree
        ev = next(e for e in ledger.items if e.source_kind == "crustdata_company_enrich" and e.field_path == "headcount.total")
        ev.value_observed = str(enriched.employee_count + 5)
    for e in ledger.items:
        e.status = "supported"
    found = find_contradictions(ledger.items)
    assert any("Headcount" in c for c in found)
    conflicted = [e for e in ledger.items if e.status == "conflicting"]
    assert len(conflicted) == 2 and conflicted[0].contradiction_with == [conflicted[1].evidence_id]


def test_rollup_takes_worst_status():
    ledger, *_ = build(fresh_ts())
    by = {e.evidence_id: e for e in ledger.items}
    ids = [e.evidence_id for e in ledger.items[:3]]
    for i in ids:
        by[i].status = "supported"
    assert rollup(ids, by) == "supported"
    by[ids[1]].status = "stale"
    assert rollup(ids, by) == "stale"
    by[ids[2]].status = "unsupported"
    assert rollup(ids, by) == "unsupported"
    assert rollup([], by) == "unverified"


def full_verify(tamper_sizing=False, tamper_score=False):
    ledger, cs, enriched, ceo = build(fresh_ts())
    ranked = score_and_rank([c for c in cs], brief())
    sizing = compute_sizing(brief(), 2410, ranked)
    if tamper_sizing:
        sizing.pool += 1
    if tamper_score:
        ranked[0].fit_score += 5
    eligible = sum(1 for c in ranked if c.wave)
    auq = next(c for c in ranked if c.company_id == "6507")
    rep = verify_mission(brief(), ledger, ranked, {"6507": [ceo]}, sizing, eligible)
    return rep, ledger, ranked, ceo, auq


def test_verify_mission_clean_run():
    rep, ledger, ranked, ceo, auq = full_verify()
    assert rep.arithmetic_errors == [] and rep.score_mismatches == [] and rep.duplicate_accounts == []
    # the enrich-sourced evidence is not in any ranked company's ids here, but search evidence all verifies
    assert rep.verified_fraction is not None and rep.verified_fraction > 0.9
    assert all(c.verification_status == "supported" for c in ranked)
    assert ceo.verification_status == "supported"
    assert any(e.subject_type == "calc" and e.status == "supported" for e in ledger.items)


def test_tampered_arithmetic_and_score_are_caught():
    rep, ledger, *_ = full_verify(tamper_sizing=True)
    assert rep.arithmetic_errors and any("arithmetic" in w for w in rep.warnings())
    assert any(e.subject_type == "calc" and e.status == "unsupported" for e in ledger.items)
    rep2, *_ = full_verify(tamper_score=True)
    assert rep2.score_mismatches
