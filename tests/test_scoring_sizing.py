import pytest

from marketentry.brief_parser import parse_brief
from marketentry.contracts import CompanyRecord, IdentityMatch, MarketBrief
from marketentry.normalizers import normalize_company
from marketentry.scoring import assign_wave, score_and_rank, score_company
from marketentry.sizing import compute_sizing, verify_sizing

from .conftest import fixture


def brief(**kw):
    base = dict(product_name="P", product_description="security compliance software", target_country="United Kingdom",
                target_industry="FinTech", employee_min=50, employee_max=500, annual_contract_value=12000.0,
                currency="GBP", competitor_keywords=["compliance automation"])
    return MarketBrief(**{**base, **kw})


def co(**kw):
    base = dict(name="Acme", company_id="1", country="GBR", employee_count=200,
                identity=IdentityMatch(method="company_id", confidence=1.0))
    return CompanyRecord(**{**base, **kw})


def test_unknown_components_are_none_not_zero_and_coverage_is_separate():
    s = score_company(co(), brief())
    assert s.score_breakdown["growth"] is None and s.score_breakdown["hiring"] is None
    assert s.score_breakdown["need"] is None and s.score_breakdown["buyer"] is None
    assert s.score_breakdown["icp_country"] == 10 and s.score_breakdown["icp_headcount"] == 15
    assert s.data_coverage == 0.35 and s.fit_score == 100.0 and s.confidence == "low"
    assert {"unknown:growth", "unknown:hiring", "unknown:buyer"} <= set(s.flags)


def test_observed_zero_differs_from_unknown():
    s = score_company(co(headcount_growth_6m=-5.0, open_roles=0), brief())
    assert s.score_breakdown["growth"] == 0 and s.score_breakdown["hiring"] == 0
    assert s.fit_score < 100


def test_growth_and_hiring_scaling():
    s = score_company(co(headcount_growth_6m=10.0, open_roles=10), brief())  # 10/200=5% of 10% => half
    assert s.score_breakdown["growth"] == 10.0 and s.score_breakdown["hiring"] == 7.5
    assert score_company(co(headcount_growth_6m=80.0), brief()).score_breakdown["growth"] == 20


def test_out_of_icp_gets_no_wave():
    big = score_company(co(employee_count=5000), brief())
    assert big.icp_match is False and assign_wave(big) is None
    wrong = score_company(co(country="DEU"), brief())
    assert wrong.icp_match is False and wrong.score_breakdown["icp_country"] == 0


def test_need_uses_description_terms_only():
    r = co(description="We build compliance automation and security tooling for banks")
    s = score_company(r, brief())
    assert s.score_breakdown["need"] == 15.0
    assert score_company(co(description="Coffee roasters"), brief()).score_breakdown["need"] == 0


def test_wave_rules():
    full = co(headcount_growth_6m=20.0, open_roles=20, description="compliance automation security software",
              buyer_status="found")
    s = score_company(full, brief())
    assert s.confidence == "high" and assign_wave(s) == "Wave 1"
    nobuyer = score_company(co(headcount_growth_6m=20.0, open_roles=20, description="security compliance software",
                               buyer_status="buyer_not_found"), brief())
    assert assign_wave(nobuyer) == "Wave 2"  # fit still high but no buyer
    unresolved = score_company(co(identity=IdentityMatch(), company_id=None), brief())
    assert assign_wave(unresolved) == "Research Needed"
    thin = score_company(co(country=None, employee_count=None), brief())  # coverage 0.1
    assert assign_wave(thin) == "Research Needed"


def test_ranking_is_deterministic_and_input_not_mutated():
    a, b = co(name="B", headcount_growth_6m=20.0), co(name="A", headcount_growth_6m=20.0)
    before = a.model_dump()
    out = score_and_rank([a, b], brief())
    assert [r.name for r in out] == ["A", "B"] and a.model_dump() == before


def test_scores_real_fixture_records():
    recs = [normalize_company(c) for c in fixture("company_search_uk_fin")["body"]["companies"]]
    out = score_and_rank(recs, brief(employee_min=0, employee_max=1000))
    assert all(r.fit_score is not None and 0 <= r.fit_score <= 100 for r in out)
    assert all(r.score_breakdown["icp_country"] == 10 for r in out)  # GBR vs United Kingdom


# ---- sizing -----------------------------------------------------------------
def test_sizing_formula_and_arithmetic():
    sl = score_and_rank([co(name=str(i), company_id=str(i), headcount_growth_6m=10.0) for i in range(3)], brief())
    s = compute_sizing(brief(), 517, sl)
    assert s.pool == 517 * 12000 and s.pipeline_pool == 36000
    assert "517 indexed companies × GBP 12,000 ACV = GBP 6,204,000" in s.formula_text
    assert any("not TAM" in c for c in s.caveats)
    assert verify_sizing(s, 3) == []
    s.pool += 1
    assert verify_sizing(s, 3)


def test_no_acv_means_no_money():
    s = compute_sizing(brief(annual_contract_value=None, currency=None), 290, [])
    assert s.pool is None and s.pipeline_pool is None and s.observed_count == 290
    assert "No ACV supplied" in s.formula_text and verify_sizing(s, 0) == []


def test_unknown_count_and_unresolved_accounts_excluded():
    unresolved = score_and_rank([co(identity=IdentityMatch(), company_id=None)], brief())
    s = compute_sizing(brief(), None, unresolved, post_filters=["employee_max"])
    assert s.pool is None and s.pipeline_pool == 0
    assert any("total_count" in c for c in s.caveats) and any("post-filters" in c for c in s.caveats)


def test_end_to_end_parse_to_size():
    b = parse_brief("We sell routing software to logistics companies. Entry into Germany, 100-1,000 employees, €9,000 ACV.")
    assert compute_sizing(b, 290, []).pool == 290 * 9000
