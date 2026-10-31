import pytest
from pydantic import ValidationError

from marketentry.contracts import (CompanyRecord, MarketBrief, MissionResult, PersonRecord, ToolRun)


def test_company_defaults_are_unknown_not_zero():
    c = CompanyRecord(name="X")
    assert c.employee_count is None and c.fit_score is None and c.open_roles is None
    assert c.verification_status == "unverified" and c.buyer_status == "not_searched"
    assert c.identity.method == "unresolved"


def test_person_has_no_email_field():
    assert not any("email" in f for f in PersonRecord.model_fields)


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        CompanyRecord(name="X", invented_field=1)


def test_brief_range_validation_and_unset_acv():
    b = MarketBrief(product_name="P", product_description="d", target_country="UK", target_industry="Fintech",
                    employee_min=50, employee_max=500)
    assert b.annual_contract_value is None  # never invented
    with pytest.raises(ValidationError):
        MarketBrief(product_name="P", product_description="d", target_country="UK", target_industry="F",
                    employee_min=500, employee_max=50)


def test_toolrun_status_enum_and_mission_result():
    with pytest.raises(ValidationError):
        ToolRun(run_id="r", mission_id="m", tool_name="t", endpoint="GET /x", request_hash="h",
                result_status="weird", started_at_utc="now")
    assert MissionResult(mission_id="m", state="partial").warnings == []
