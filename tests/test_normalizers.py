import pytest

from marketentry.evidence import EvidenceLedger
from marketentry.normalizers import (country_matches, dig, domain_from_url, match_role, merge_company,
                                     normalize_company, normalize_person, resolve_identify_entry,
                                     unwrap_envelope)

from .conftest import fixture


def search_item(i=0):
    return fixture("company_search_uk_fin")["body"]["companies"][i]


def enrich_data():
    return fixture("company_enrich_auquan")["body"][0]["matches"][0]["company_data"]


def test_search_record_maps_only_present_fields():
    raw = search_item(0)
    c = normalize_company(raw)
    assert c.company_id == "713" and c.name == "Bits" and c.domain == "getbits.app"
    assert c.country == "GBR" and c.employee_count == dig(raw, "headcount.total")
    assert c.headcount_growth_6m == dig(raw, "headcount.growth_percent.6m")
    assert c.employee_range == "11-50"
    # not requested in the search => null, never 0
    assert c.open_roles is None and c.funding_total is None and c.industry is None
    assert c.identity.method == "company_id" and c.enriched is False
    assert 0 < c.data_coverage < 1


def test_enrich_uses_enrich_specific_growth_keys_and_hiring():
    raw = enrich_data()
    c = normalize_company(raw, enriched=True)
    assert c.company_id == "6507" and c.name == "Auquan" and c.enriched
    assert c.headcount_growth_6m == raw["headcount"]["growth_percent"]["six_months"]
    assert c.headcount_growth_12m == raw["headcount"]["growth_percent"]["yoy"]
    assert c.open_roles == raw["hiring"]["openings_count"]
    assert c.funding_total == raw["funding"]["total_investment_usd"]
    assert c.country is None  # `locations` not requested in this enrich


def test_empty_and_wrong_typed_values_become_null():
    c = normalize_company({"crustdata_company_id": 5, "basic_info": {"name": "  ", "primary_domain": 7},
                           "headcount": {"total": "many", "growth_percent": {"6m": None}},
                           "hiring": {"openings_count": True}})
    assert c.name == "unknown (id 5)" and "name_missing" in c.flags
    assert c.domain is None and c.employee_count is None and c.headcount_growth_6m is None and c.open_roles is None


def test_record_without_id_is_unresolved():
    c = normalize_company({"basic_info": {"name": "NoId Ltd"}})
    assert c.company_id is None and c.identity.method == "unresolved" and "no_canonical_id" in c.flags


def test_merge_enrich_over_search_flags_conflicts_and_keeps_ids():
    ledger = EvidenceLedger("m")
    s = normalize_company(search_item(1), ledger=ledger, source_kind="crustdata_company_search")
    e = normalize_company(enrich_data(), enriched=True, ledger=ledger, source_kind="crustdata_company_enrich")
    assert s.company_id == e.company_id == "6507"
    m = merge_company(s, e)
    assert m.enriched and m.open_roles == e.open_roles and m.country == s.country  # union of both sources
    assert set(s.evidence_ids) | set(e.evidence_ids) == set(m.evidence_ids)
    if s.employee_count != e.employee_count:
        assert any(f.startswith("conflict:employee_count") for f in m.flags)
    with pytest.raises(ValueError):
        merge_company(s, normalize_company(search_item(0)))


def test_evidence_has_field_path_and_value_for_every_claim():
    ledger = EvidenceLedger("m1")
    c = normalize_company(search_item(0), ledger=ledger, raw_ref="fixtures/raw/company_search_uk_fin.json",
                          retrieved_at="2026-10-31T05:00:00+00:00")
    assert len(ledger.items) == len(c.evidence_ids) > 0
    by_path = {e.field_path: e for e in ledger.items}
    assert by_path["headcount.total"].value_observed == str(c.employee_count)
    assert all(e.status == "supported" and e.raw_ref and e.retrieved_at_utc.startswith("2026-10-31")
               for e in ledger.items)
    assert "hiring.openings_count" not in by_path  # no evidence for absent fields


# ---- identity --------------------------------------------------------------
def test_identify_by_domain_resolves_uniquely():
    entry = unwrap_envelope(fixture("company_identify_domain")["body"])[0]
    c, ident = resolve_identify_entry(entry)
    assert c and c.company_id == "6507" and ident.method == "domain" and ident.confidence == 1.0


def test_name_only_match_is_rejected_the_bits_university_case():
    entry = unwrap_envelope(fixture("company_identify_name_ambig")["body"])[0]
    assert entry["matches"][0]["confidence_score"] == 1.0  # provider is "certain"...
    c, ident = resolve_identify_entry(entry)
    assert c is None and ident.method == "unresolved" and "domain verification" in ident.decision_note
    assert dig(entry["matches"][0]["company_data"], "basic_info.primary_domain") == "bits-pilani.ac.in"
    # with the expected fintech domain, the right candidate further down the list is chosen, not the university
    c2, ident2 = resolve_identify_entry(entry, expected_domain="getbits.app")
    assert c2 and c2.company_id == "713" and ident2.method == "domain"
    # a domain no candidate has stays unresolved
    c3, ident3 = resolve_identify_entry(entry, expected_domain="nothere.example")
    assert c3 is None and "no candidate has domain nothere.example" in ident3.decision_note


def test_expected_domain_verifies_a_name_candidate():
    entry = {"match_type": "name", "matches": [
        {"confidence_score": 0.8, "company_data": {"crustdata_company_id": 9, "basic_info": {"name": "Acme", "primary_domain": "acme.io"}}}]}
    c, ident = resolve_identify_entry(entry, expected_domain="https://www.acme.io/about")
    assert c and c.company_id == "9" and ident.method == "domain"


def test_no_match_and_ambiguous_domain():
    assert resolve_identify_entry({"match_type": "domain", "matches": []})[0] is None
    two = {"match_type": "domain", "matches": [
        {"confidence_score": 1.0, "company_data": {"crustdata_company_id": 1, "basic_info": {"primary_domain": "x.com"}}},
        {"confidence_score": 1.0, "company_data": {"crustdata_company_id": 2, "basic_info": {"primary_domain": "x.com"}}}]}
    c, ident = resolve_identify_entry(two)
    assert c is None and "ambiguous" in ident.decision_note


def test_unwrap_envelope_tolerates_bad_shapes():
    assert unwrap_envelope({"error": "x"}) == [] and unwrap_envelope(None) == []


# ---- people ----------------------------------------------------------------
def person_raw(i=0):
    return fixture("person_search_auquan_any")["body"]["profiles"][i]


def test_person_employer_verified_by_company_id():
    company = normalize_company(enrich_data(), enriched=True)
    ledger = EvidenceLedger("m")
    p = normalize_person(person_raw(0), company, ["CEO", "Head of Compliance"], ledger=ledger)
    assert p.name == "Chandini Jain" and p.person_id == "96842"
    assert p.employer_verified and p.verification_method == "id" and p.verification_status == "supported"
    assert p.current_employer_company_id == "6507" and p.current_employer_domain == "auquan.com"
    assert p.role_matched == "CEO" and p.employment_start is None
    assert "employment_start_missing" in p.missing_flags and "linkedin_url_missing" in p.missing_flags
    assert {e.field_path for e in ledger.items} >= {"basic_profile.current_title"}
    assert not any("email" in f for f in PersonRecordFields())


def PersonRecordFields():
    from marketentry.contracts import PersonRecord
    return PersonRecord.model_fields


def test_person_at_other_company_is_not_verified():
    other = normalize_company(search_item(0))  # Bits, id 713
    p = normalize_person(person_raw(0), other, ["CEO"])
    assert not p.employer_verified and p.verification_method == "none" and p.verification_status == "unverified"
    assert "employer_not_verified" in p.missing_flags


def test_person_domain_fallback_when_no_id_match():
    company = normalize_company({"crustdata_company_id": 999, "basic_info": {"name": "Auquan", "primary_domain": "auquan.com"}})
    p = normalize_person(person_raw(0), company, ["CEO"])
    assert p.employer_verified and p.verification_method == "domain"


def test_person_title_not_matching_roles_is_flagged_not_dropped():
    company = normalize_company(enrich_data())
    p = normalize_person(person_raw(0), company, ["Head of Compliance"])
    assert p.role_matched is None and "title_not_matching_target_roles" in p.missing_flags


def test_person_with_empty_record_degrades_to_nulls():
    p = normalize_person({}, normalize_company(enrich_data()), ["CEO"])
    assert p.name == "unknown" and p.current_title is None and not p.employer_verified
    assert {"title_missing", "employer_not_verified"} <= set(p.missing_flags)


def test_match_role_expands_abbreviations():
    assert match_role("Chief Information Security Officer", ["CISO"]) == "CISO"
    assert match_role("VP, Security Engineering", ["VP Security"]) == "VP Security"
    assert match_role("Head of Compliance & Risk", ["Head of Compliance"]) == "Head of Compliance"
    assert match_role("Software Engineer", ["CISO"]) is None and match_role(None, ["CISO"]) is None


def test_helpers():
    assert domain_from_url("http://www.getbits.app/x?y=1") == "getbits.app" and domain_from_url(None) is None
    assert country_matches("United Kingdom", "GBR") is True and country_matches("Germany", "GBR") is False
    assert country_matches("United Kingdom", None) is None and country_matches("Narnia", "XYZ") is None
