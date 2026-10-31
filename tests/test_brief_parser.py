import json

import httpx

from marketentry.brief_parser import parse_brief, parse_acv, parse_employees
from marketentry.config import Settings
from marketentry.llm import LLMClient

SPEC = ("We sell cybersecurity compliance software for financial technology companies. Evaluate entry into the UK "
        "fintech market. Focus on companies with 50–500 employees. Estimate the addressable company universe using a "
        "£12,000 annual contract value assumption; identify competitors and buyer roles; produce a ranked "
        "target-account shortlist.")
DE = ("We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, "
      "100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO.")


def test_spec_example_rules_only():
    b = parse_brief(SPEC)
    assert b.target_country == "United Kingdom" and b.target_industry == "FinTech"  # not Cybersecurity
    assert (b.employee_min, b.employee_max) == (50, 500)
    assert b.annual_contract_value == 12000 and b.currency == "GBP"
    assert b.product_description == "cybersecurity compliance software"
    src = {a.field: a.source for a in b.assumptions}
    assert src["target_buyer_roles"] == "defaulted" and src["annual_contract_value"] == "user"


def test_unseen_german_logistics_prompt():
    b = parse_brief(DE)
    assert b.target_country == "Germany" and b.target_industry == "Logistics"
    assert (b.employee_min, b.employee_max) == (100, 1000)
    assert b.annual_contract_value == 9000 and b.currency == "EUR"
    assert b.target_buyer_roles == ["Head of Fleet", "VP Operations", "CTO"]


def test_missing_acv_is_null_never_invented():
    b = parse_brief("We sell payroll software to e-commerce firms. Evaluate entry into Singapore for 50-500 employees.")
    assert b.annual_contract_value is None and b.currency is None
    assert b.target_country == "Singapore" and b.target_industry == "E-Commerce"
    a = next(a for a in b.assumptions if a.field == "annual_contract_value")
    assert a.source == "defaulted" and "omitted" in a.note


def test_unrecognised_market_is_flagged_not_guessed():
    b = parse_brief("Help me sell stuff somewhere nice.")
    assert b.target_country == "unknown" and b.target_industry == "unknown"
    assert any("country" in u for u in b.unsupported_constraints)


def test_inverted_range_dropped_with_flag():
    b = parse_brief("Entry into India for healthcare, 500-50 employees.")
    assert b.employee_min is None and b.employee_max is None
    assert any("inverted" in u for u in b.unsupported_constraints)


def test_number_helpers():
    assert parse_acv("ACV of ₹12k") == (12000.0, "INR") and parse_acv("9,500 USD per year") == (9500.0, "USD")
    assert parse_acv("no money here") == (None, None)
    assert parse_employees("more than 200 employees") == (200, None)
    assert parse_employees("between 50 and 500 employees") == (50, 500)


def test_overrides_win_and_are_labelled_user():
    b = parse_brief(SPEC, overrides={"max_target_accounts": 8, "annual_contract_value": 5000.0})
    assert b.max_target_accounts == 8 and b.annual_contract_value == 5000.0
    assert any(a.field == "max_target_accounts" and a.source == "user" for a in b.assumptions)


def _llm(handler, key="k"):
    s = Settings(_env_file=None, llm_api_key=key, llm_base_url="https://llm.test/v1")
    return LLMClient(s, transport=httpx.MockTransport(handler), sleep=lambda x: None)


def reply(obj):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(obj)}}]})


def test_llm_fills_text_fields_but_never_numbers():
    llm = _llm(lambda r: reply({"product_name": "FleetPilot", "target_industry": "Freight", "annual_contract_value": 99999,
                                "employee_min": 1, "competitor_keywords": ["fleet maintenance", "predictive maintenance"],
                                "target_country": "Atlantis"}))
    b = parse_brief("We sell fleet tooling to haulage firms. Evaluate entry into Germany.", llm)
    assert b.product_name == "FleetPilot" and b.competitor_keywords[0] == "fleet maintenance"
    assert b.target_industry == "Freight"  # rules found no sector; LLM text accepted + labelled
    assert next(a for a in b.assumptions if a.field == "target_industry").source == "inferred"
    assert b.annual_contract_value is None and b.employee_min is None  # numbers ignored
    assert b.target_country == "Germany"  # rules win; invented country ignored


def test_llm_failure_falls_back_to_rules():
    llm = _llm(lambda r: httpx.Response(500, text="boom"))
    b = parse_brief(DE, llm)
    assert b.target_country == "Germany" and llm.runs[-1]["ok"] is False


def test_llm_unavailable_without_key_makes_no_call():
    def boom(r):
        raise AssertionError("called")
    llm = _llm(boom, key=None)
    assert not llm.available and llm.complete_text("s", "u", purpose="x") is None
    assert parse_brief(DE, llm).target_country == "Germany"
