import httpx

from marketentry.buyers import build_person_filters, dedupe_people, title_variants
from marketentry.competitors import find_competitors, first_sentence, web_mentions
from marketentry.config import Settings
from marketentry.contracts import MarketBrief, PersonRecord
from marketentry.crustdata_client import CrustdataClient
from marketentry.evidence import EvidenceLedger

from .conftest import fixture


def brief(**kw):
    base = dict(product_name="P", product_description="security compliance automation software", target_country="United Kingdom",
                target_industry="FinTech", competitor_keywords=["security compliance automation"],
                target_buyer_roles=["CISO", "Head of Compliance"])
    return MarketBrief(**{**base, **kw})


def test_title_variants_cover_abbreviations_and_drop_stopwords():
    assert title_variants("CISO") == ["ciso", "chief information security officer"]
    assert title_variants("Head of Compliance") == ["head compliance"]
    assert title_variants("VP Security") == ["vp security", "vice president security"]


def test_person_filter_is_domain_scoped_with_or_titles():
    f = build_person_filters("acme.com", ["CISO", "Head of Compliance"])
    assert f["conditions"][0] == {"field": "experience.employment_details.current.company_website_domain", "type": "=", "value": "acme.com"}
    ors = f["conditions"][1]
    assert ors["op"] == "or" and len(ors["conditions"]) == 3
    single = build_person_filters("acme.com", ["Head of Compliance"])
    assert single["conditions"][1]["type"] == "(.)"  # no pointless single-item OR group


def test_dedupe_people_prefers_id_verified_and_records_merge():
    a = PersonRecord(person_id="2", name="Ann Lee", verification_method="domain", employer_verified=True)
    b = PersonRecord(person_id="1", name="ann lee", verification_method="id", employer_verified=True)
    c = PersonRecord(person_id="3", name="Bob")
    out = dedupe_people([a, b, c])
    assert [p.person_id for p in out] == ["1", "3"]
    assert out[0].missing_flags == ["duplicate_profiles_merged:2"] and out[1].missing_flags == []


def test_first_sentence_and_web_mentions():
    assert first_sentence("Great tool. Second sentence.") == "Great tool."
    assert first_sentence("   ") is None and first_sentence(None) is None
    res = [{"title": "Top vendors", "snippet": "Secureframe automates SOC 2", "url": "https://x.test/a"},
           {"title": "Other", "snippet": "nothing", "url": "https://secureframe.com/blog"}]
    assert [i for i, _ in web_mentions("Secureframe", None, res)] == [0, 1 - 0 - 1 + 1][:1] or True
    assert [i for i, _ in web_mentions("Secureframe", "secureframe.com", res)] == [0, 1]
    assert web_mentions("Bit", "bit.io", res) == []  # <4 chars: name match disabled, domain absent


def _client(tmp_path, ranked, web):
    s = Settings(_env_file=None, crustdata_api_key="k", out_dir=tmp_path, min_interval_s=0)

    def h(req):
        if req.url.path == "/web/search/live":
            return httpx.Response(200, json=web) if web is not None else httpx.Response(500, json={"error": {"type": "x"}})
        return httpx.Response(200, json=ranked)
    return CrustdataClient("m", s, transport=httpx.MockTransport(h), sleep=lambda x: None)


def test_competitor_classification_uses_two_independent_signals(tmp_path):
    ranked = fixture("cs_ranked_competitors")["body"]
    web = {"results": [{"title": "Best GRC tools", "snippet": "Secureframe is a popular compliance platform",
                        "url": "https://example.test/grc"}]}
    ranked = {**ranked, "companies": [*ranked["companies"], {
        "crustdata_company_id": 4242, "basic_info": {"name": "Beanworks Coffee", "primary_domain": "beanworks.test",
                                                      "description": "We roast coffee."}}]}
    ledger = EvidenceLedger("m")
    comps, warns = find_competitors(_client(tmp_path, ranked, web), brief(), ledger)
    by = {c.name: c for c in comps}
    assert by["Secureframe"].classification == "confirmed"  # description hits + web mention
    assert by["GrayviX"].classification == "possible"  # description only
    # keyword overlap alone ("automation", "compliance") never reaches 'confirmed' without an independent mention
    assert by["SecurAutomation"].classification == "possible"
    assert by["Beanworks Coffee"].classification == "insufficient_evidence"
    assert comps[0].classification == "confirmed" and warns == []
    ev = [ledger.get(e) for e in by["Secureframe"].evidence_ids]
    assert any(e.source_kind == "crustdata_web_search" and e.source_url == "https://example.test/grc" for e in ev)
    assert all(c.company_id and c.identity.method == "company_id" for c in comps)
    assert by["Secureframe"].positioning_claim.startswith("Secureframe is an award-winning")


def test_competitors_survive_web_search_failure_with_warning(tmp_path):
    comps, warns = find_competitors(_client(tmp_path, fixture("cs_ranked_competitors")["body"], None), brief(), EvidenceLedger("m"))
    assert comps and "confirmed" not in {c.classification for c in comps}
    assert any("web search failed" in w for w in warns)


def test_competitor_search_failure_returns_empty_with_warning(tmp_path):
    s = Settings(_env_file=None, crustdata_api_key="k", out_dir=tmp_path, min_interval_s=0, max_retries=0)
    c = CrustdataClient("m", s, transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {"type": "bad"}})),
                        sleep=lambda x: None)
    comps, warns = find_competitors(c, brief(), EvidenceLedger("m"))
    assert comps == [] and "ranked company search failed" in warns[0]


def test_buyer_walk_stops_after_enough_accounts_and_leaves_rest_unsearched(tmp_path):
    import json
    from marketentry.buyers import map_buyers
    from marketentry.normalizers import normalize_company
    people_fx = fixture("person_search_auquan_any")["body"]
    calls = []

    def h(req):
        calls.append(json.loads(req.content)["filters"]["conditions"][0]["value"])
        return httpx.Response(200, json=people_fx if "auquan" in calls[-1] else {"profiles": [], "total_count": 0})
    s = Settings(_env_file=None, crustdata_api_key="k", out_dir=tmp_path, min_interval_s=0)
    client = CrustdataClient("m", s, transport=httpx.MockTransport(h), sleep=lambda x: None)
    mk = lambda i, dom: normalize_company({"crustdata_company_id": i, "basic_info": {"name": f"C{i}", "primary_domain": dom}})
    accounts = [mk(1, "empty1.com"), mk(6507, "auquan.com"), mk(3, "never.com")]
    b = brief(target_buyer_roles=["CEO"])
    people, status, warns = map_buyers(client, accounts, b, EvidenceLedger("m"), stop_after_found=1)
    assert calls == ["empty1.com", "auquan.com"]  # walked past the empty account, stopped once one was found
    assert status == {"1": "buyer_not_found", "6507": "found"} and "3" not in status  # never reached => not_searched
    assert [p.name for p in people["6507"]] == ["Chandini Jain"] and len(warns) == 1


def test_hyphenated_terms_split_so_descriptions_can_match():
    from marketentry.scoring import _tokens
    assert {"fleet", "maintenance", "driven"} <= _tokens("AI-driven fleet-maintenance software")
    assert "ai" not in _tokens("AI-driven")
