import json

import httpx
import pytest

from marketentry.config import Settings
from marketentry.crustdata_client import ConfigError, CrustdataClient, request_hash

from .conftest import FIX

FILTERS = {"op": "and", "conditions": [
    {"field": "locations.country", "type": "=", "value": "United Kingdom"},
    {"field": "basic_info.industries", "type": "in", "value": ["Financial Services"]},
    {"field": "headcount.total", "type": "=>", "value": 50},
    {"field": "headcount.total", "type": "=<", "value": 500}]}
FIELDS = ["basic_info", "locations", "headcount"]


def make(settings, handler, **kw):
    sleeps = []
    c = CrustdataClient("m1", settings, transport=httpx.MockTransport(handler), sleep=sleeps.append, **kw)
    return c, sleeps


def ok_handler(calls=None):
    def h(req):
        if calls is not None:
            calls.append(req)
        return httpx.Response(200, json={"companies": [{"crustdata_company_id": 1}], "total_count": 7,
                                         "next_cursor": None}, headers={"x-credits-used": "0.43"})
    return h


def test_auth_headers_and_credit_logging(settings):
    seen = []
    c, _ = make(settings, ok_handler(seen))
    r = c.company_search(FILTERS, FIELDS, limit=1)
    assert r.ok and r.run.credit_cost == 0.43 and r.run.credit_source == "response"
    assert r.run.total_count == 7 and r.run.result_count == 1 and r.run.result_status == "ok"
    h = seen[0].headers
    assert h["authorization"] == "Bearer test-secret-key-123" and h["x-api-version"] == "2025-11-01"
    assert json.loads(seen[0].content)["fields"] == FIELDS
    assert c.credits_used == pytest.approx(0.43)


def test_secret_never_in_logs_or_raw(settings, tmp_path):
    c, _ = make(settings, ok_handler())
    c.company_search(FILTERS, FIELDS)
    blob = json.dumps([r.model_dump() for r in c.tool_runs])
    for p in (tmp_path / "m1" / "raw").glob("*.json"):
        blob += p.read_text()
    assert "test-secret-key-123" not in blob
    assert "test-secret-key-123" not in repr(settings)


def test_cache_hit_makes_no_second_call(settings):
    seen = []
    c, _ = make(settings, ok_handler(seen))
    c.company_search(FILTERS, FIELDS)
    r2 = c.company_search(FILTERS, FIELDS)
    assert len(seen) == 1 and r2.ok and r2.run.result_status == "cached" and r2.run.credit_cost == 0.0
    assert c.credits_used == pytest.approx(0.43)  # cached call charged nothing


def test_retry_429_honours_retry_after_then_succeeds(settings):
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(429, json={"error": {"type": "rate_limited", "message": "slow"}},
                                  headers={"retry-after": "0.02"})
        return httpx.Response(200, json={"companies": []})
    c, sleeps = make(settings, h)
    r = c.company_search(FILTERS)
    assert r.ok and n["i"] == 2 and 0.02 in sleeps
    assert [t.result_status for t in c.tool_runs] == ["error", "empty"]
    assert c.tool_runs[0].error_type == "rate_limited" and c.tool_runs[1].attempt == 2


def test_5xx_exhausts_bounded_retries_with_exponential_backoff(settings):
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(503, text="<html>bad gateway</html>")
    c, sleeps = make(settings, h)
    r = c.company_search(FILTERS)
    assert not r.ok and n["i"] == 1 + settings.max_retries
    assert r.error_type == "http_503_non_json" and "bad gateway" in r.message
    assert len(sleeps) == settings.max_retries
    assert sleeps[1] >= sleeps[0] * 1.5  # grows
    assert c.warnings and "company_search failed" in c.warnings[-1]


def test_4xx_not_retried_and_402_type_parsed(settings):
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(402, json={"error": {"type": "insufficient_credits", "message": "top up", "metadata": []}})
    c, _ = make(settings, h)
    r = c.company_search(FILTERS)
    assert n["i"] == 1 and r.error_type == "insufficient_credits" and r.status == 402


def test_transport_error_retried_then_reported_not_raised(settings):
    def h(req):
        raise httpx.ConnectTimeout("boom")
    c, _ = make(settings, h)
    r = c.company_search(FILTERS)
    assert not r.ok and r.status is None and r.error_type == "transport_ConnectTimeout"
    assert len(c.tool_runs) == 1 + settings.max_retries


def test_weird_error_bodies_never_raise(settings):
    for payload in ([1, 2], "str", {"error": 5}, {"error": {"type": None}}):
        c, _ = make(settings, lambda req, p=payload: httpx.Response(400, json=p))
        r = c.company_search(FILTERS)
        assert not r.ok and r.error_type.startswith("http_400")


def test_simulated_transient_failure_logged_then_recovers(settings):
    s = settings.model_copy(update={"simulate_transient_failure": True})
    seen = []
    c, _ = make(s, ok_handler(seen))
    r = c.company_search(FILTERS, FIELDS)
    assert r.ok and len(seen) == 1  # only the real retry reached the network
    assert [t.result_status for t in c.tool_runs] == ["simulated_failure", "ok"]
    assert any("Simulated transient failure" in w for w in c.warnings)
    c.company_search(FILTERS, FIELDS, limit=2)  # injected only once per mission
    assert [t.result_status for t in c.tool_runs].count("simulated_failure") == 1


def test_credit_cap_and_web_cap_block_calls(settings):
    s = settings.model_copy(update={"max_credits_per_mission": 0.4, "max_web_queries": 1})
    seen = []
    c, _ = make(s, ok_handler(seen))
    c.company_search(FILTERS, FIELDS)  # spends 0.43
    r = c.company_search(FILTERS, FIELDS, limit=3)
    assert not r.ok and r.error_type == "cost_cap" and len(seen) == 1

    s2 = settings.model_copy(update={"max_web_queries": 1})
    c2, _ = make(s2, lambda req: httpx.Response(200, json={"results": []}))
    assert c2.web_search("a").ok
    assert c2.web_search("b").error_type == "cost_cap"


def test_missing_key_raises_config_error(tmp_path):
    s = Settings(_env_file=None, crustdata_api_key=None, out_dir=tmp_path)
    c = CrustdataClient("m", s, transport=httpx.MockTransport(ok_handler()))
    with pytest.raises(ConfigError):
        c.credits()


def test_identify_requires_exactly_one_identifier_type(settings):
    c, _ = make(settings, ok_handler())
    with pytest.raises(ValueError):
        c.company_identify(domains=["a.com"], names=["A"])
    with pytest.raises(ValueError):
        c.company_identify()
    with pytest.raises(ValueError):
        c.company_identify(domains=[f"{i}.com" for i in range(26)])


def test_paged_search_follows_cursor_and_keeps_partial_on_failure(settings):
    pages = {None: {"companies": [{"crustdata_company_id": 1}, {"crustdata_company_id": 2}], "next_cursor": "c1", "total_count": 9},
             "c1": {"companies": [{"crustdata_company_id": 3}], "next_cursor": "c2", "total_count": 9}}

    def h(req):
        cur = json.loads(req.content).get("cursor")
        if cur == "c2":
            return httpx.Response(400, json={"error": {"type": "bad_cursor", "message": "expired"}})
        return httpx.Response(200, json=pages[cur])
    c, _ = make(settings, h)
    items, total, warn = c.company_search_paged(FILTERS, FIELDS, max_results=10)
    assert [i["crustdata_company_id"] for i in items] == [1, 2, 3] and total == 9
    assert "bad_cursor" in warn


# ---- REPLAY ----------------------------------------------------------------
def replay_client(settings):
    s = settings.model_copy(update={"replay": True, "crustdata_api_key": None})

    def no_network(req):
        raise AssertionError("network used in replay mode")
    return CrustdataClient("m", s, transport=httpx.MockTransport(no_network), sleep=lambda x: None)


def test_replay_serves_saved_fixture_without_network_or_key(settings):
    c = replay_client(settings)
    saved = json.loads((FIX / "company_search_uk_fin.json").read_text())
    r = c.company_search(FILTERS, FIELDS, limit=3)  # identical body to the probe request
    assert r.ok and r.run.result_status == "replayed" and r.body["total_count"] == saved["body"]["total_count"]
    assert r.retrieved_at == saved["retrieved_at_utc"]


def test_replay_miss_is_an_honest_error_not_fabricated(settings):
    c = replay_client(settings)
    r = c.company_search({"field": "headcount.total", "type": "=", "value": 12345})
    assert not r.ok and r.error_type == "replay_miss" and r.body is None
    assert any("REPLAY" in w for w in c.warnings)


def test_request_hash_is_order_insensitive_but_body_sensitive():
    assert request_hash("post", "/x", {"a": 1, "b": 2}) == request_hash("POST", "/x", {"b": 2, "a": 1})
    assert request_hash("POST", "/x", {"a": 1}) != request_hash("POST", "/x", {"a": 2})
