"""Crustdata HTTP client: auth from env, per-mission cache, bounded retries, safe error parsing,
tool_runs logging, REPLAY from fixtures/raw, and a demo-only transient-failure injector."""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import httpx

from .config import Settings, get_settings
from .contracts import ToolRun
from .evidence import utcnow

# Response headers worth keeping in recorded raw files (never request headers).
_KEEP_HEADERS = ("x-credits-used", "retry-after", "content-type")


class ConfigError(RuntimeError):
    pass


def request_hash(method: str, path: str, body: Any) -> str:
    blob = json.dumps({"m": method.upper(), "p": path, "b": body}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass
class CallResult:
    ok: bool
    status: int | None
    body: Any
    run: ToolRun
    error_type: str | None = None
    message: str | None = None
    retrieved_at: str = field(default_factory=utcnow)


def _parse_body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"_non_json_body": resp.text[:500]}


def _error_info(status: int | None, body: Any) -> tuple[str, str | None]:
    """(error_type, message) from an error body of unknown shape. Never raises."""
    try:
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return str(err.get("type") or f"http_{status}"), (str(err.get("message"))[:300] if err.get("message") else None)
        if isinstance(err, str):
            return f"http_{status}", err[:300]
        if isinstance(body, dict) and "_non_json_body" in body:
            return f"http_{status}_non_json", body["_non_json_body"][:200]
    except Exception:
        pass
    return f"http_{status}", None


def _counts(body: Any) -> tuple[int | None, int | None]:
    """(result_count, total_count) for the response shapes seen so far."""
    if isinstance(body, dict):
        total = body.get("total_count")
        total = total if isinstance(total, int) else None
        for k in ("companies", "profiles", "results"):
            if isinstance(body.get(k), list):
                return len(body[k]), total
        return None, total
    if isinstance(body, list):  # identify / enrich envelope
        if all(isinstance(e, dict) and "matches" in e for e in body):
            return sum(len(e.get("matches") or []) for e in body), None
        return len(body), None
    return None, None


class CrustdataClient:
    def __init__(
        self,
        mission_id: str,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_run: Callable[[ToolRun], None] | None = None,
    ):
        self.mission_id = mission_id
        self.s = settings or get_settings()
        self._sleep = sleep
        self._on_run = on_run
        self._http = httpx.Client(base_url=self.s.base_url, timeout=self.s.timeout_s, transport=transport)
        self._cache: dict[str, CallResult] = {}
        self._replay_index: dict[str, dict] | None = None
        self._simulated = False
        self._last_call = 0.0
        self.tool_runs: list[ToolRun] = []
        self.search_pages: list[tuple[str | None, str, int]] = []
        self.warnings: list[str] = []
        self.credits_used = 0.0
        self._calls: dict[str, int] = {}

    # ---- low level ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        key = self.s.api_key()
        if not key:
            raise ConfigError("CRUSTDATA_API_KEY is not set (env or .env)")
        return {
            "Authorization": f"Bearer {key}",
            "x-api-version": self.s.api_version,
            "Content-Type": "application/json",
        }

    def _log(self, tool, method, path, h, body, status, *, http_status=None, attempt=1, t0=None,
             credit=None, resp_body=None, error_type=None, raw_path=None) -> ToolRun:
        rc, tc = _counts(resp_body)
        if status == "ok" and rc == 0:
            status = "empty"
        run = ToolRun(
            run_id=f"run_{len(self.tool_runs) + 1:04d}",
            mission_id=self.mission_id,
            tool_name=tool,
            endpoint=f"{method.upper()} {path}",
            request_hash=h,
            request_summary=json.dumps(body, sort_keys=True, default=str)[:500] if body is not None else "",
            result_status=status,
            http_status=http_status,
            attempt=attempt,
            duration_ms=int((time.monotonic() - t0) * 1000) if t0 else 0,
            credit_cost=credit,
            credit_source="response" if credit is not None else "unknown",
            result_count=rc,
            total_count=tc,
            error_type=error_type,
            raw_path=raw_path,
            started_at_utc=utcnow(),
        )
        self.tool_runs.append(run)
        if self._on_run:
            self._on_run(run)
        return run

    def _record_raw(self, tool, method, path, h, body, resp: httpx.Response, resp_body, retrieved_at) -> str | None:
        if not self.s.record_raw:
            return None
        d = Path(self.s.out_dir) / self.mission_id / "raw"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{tool}_{h[:10]}.json"
        p.write_text(json.dumps({
            "name": p.stem,
            "endpoint": f"{method.upper()} {path}",
            "request": body,
            "http_status": resp.status_code,
            "response_headers": {k: v for k, v in resp.headers.items()
                                 if k.lower() in _KEEP_HEADERS or k.lower().startswith("x-ratelimit")},
            "retrieved_at_utc": retrieved_at,
            "body": resp_body,
        }, indent=2, ensure_ascii=False))
        return str(p)

    def _pace(self) -> None:
        wait = self.s.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.s.backoff_max_s)
            except ValueError:
                pass
        base = min(self.s.backoff_max_s, self.s.backoff_base_s * 2 ** (attempt - 1))
        return base + random.uniform(0, 0.25 * base)

    # ---- replay ------------------------------------------------------------
    def _load_replay_index(self) -> dict[str, dict]:
        idx: dict[str, dict] = {}
        for p in sorted(Path(self.s.fixtures_dir).glob("*.json")):
            try:
                rec = json.loads(p.read_text())
                method, path = rec["endpoint"].split(" ", 1)
                idx[request_hash(method, path, rec.get("request"))] = {**rec, "_file": str(p)}
            except Exception:
                continue
        return idx

    def _replay(self, tool, method, path, h, body) -> CallResult:
        if self._replay_index is None:
            self._replay_index = self._load_replay_index()
        rec = self._replay_index.get(h)
        t0 = time.monotonic()
        if rec is None:
            run = self._log(tool, method, path, h, body, "error", t0=t0, error_type="replay_miss")
            self.warnings.append(f"REPLAY: no fixture for {tool} {run.request_summary[:80]}")
            return CallResult(False, None, None, run, "replay_miss", "no matching fixture in fixtures/raw")
        status = rec.get("http_status")
        ok = status is not None and 200 <= status < 300
        et, msg = (None, None) if ok else _error_info(status, rec.get("body"))
        run = self._log(tool, method, path, h, body, "replayed" if ok else "error", http_status=status,
                        t0=t0, credit=0.0, resp_body=rec.get("body"), error_type=et, raw_path=rec["_file"])
        return CallResult(ok, status, rec.get("body"), run, et, msg, rec.get("retrieved_at_utc") or utcnow())

    # ---- main entry --------------------------------------------------------
    def request(self, tool: str, method: str, path: str, body: Any = None) -> CallResult:
        h = request_hash(method, path, body)

        if h in self._cache:
            hit = self._cache[h]
            run = self._log(tool, method, path, h, body, "cached", http_status=hit.status, credit=0.0,
                            resp_body=hit.body, raw_path=hit.run.raw_path)
            return CallResult(True, hit.status, hit.body, run, retrieved_at=hit.retrieved_at)

        if self.s.replay:
            res = self._replay(tool, method, path, h, body)
            if res.ok:
                self._cache[h] = res
            return res

        # cost caps (checked before spending)
        capped = None
        if self.credits_used >= self.s.max_credits_per_mission:
            capped = f"credit cap {self.s.max_credits_per_mission} reached"
        elif tool == "web_search" and self._calls.get(tool, 0) >= self.s.max_web_queries:
            capped = f"max_web_queries {self.s.max_web_queries} reached"
        if capped:
            self.warnings.append(f"{tool} skipped: {capped}")
            run = self._log(tool, method, path, h, body, "error", error_type="cost_cap")
            return CallResult(False, None, None, run, "cost_cap", capped)
        self._calls[tool] = self._calls.get(tool, 0) + 1

        headers = self._headers()  # raises ConfigError before any network use
        max_attempts = 1 + self.s.max_retries
        res: CallResult | None = None
        for attempt in range(1, max_attempts + 1):
            t0 = time.monotonic()
            if self.s.simulate_transient_failure and not self._simulated and tool != "account_credits":
                self._simulated = True
                run = self._log(tool, method, path, h, body, "simulated_failure", http_status=503,
                                attempt=attempt, t0=t0, error_type="simulated_transient_failure")
                self.warnings.append(f"Simulated transient failure injected on {tool} (attempt {attempt}); retrying")
                res = CallResult(False, 503, None, run, "simulated_transient_failure", "injected for demo")
                self._sleep(self._delay(attempt, None))
                continue

            self._pace()
            try:
                resp = self._http.request(method.upper(), path, headers=headers,
                                          json=body if body is not None else None)
            except httpx.TransportError as e:
                et = f"transport_{type(e).__name__}"
                run = self._log(tool, method, path, h, body, "error", attempt=attempt, t0=t0, error_type=et)
                res = CallResult(False, None, None, run, et, "network error")
                if attempt < max_attempts:
                    self._sleep(self._delay(attempt, None))
                continue

            resp_body = _parse_body(resp)
            retrieved = utcnow()
            credit = None
            try:
                if "x-credits-used" in resp.headers:
                    credit = float(resp.headers["x-credits-used"])
            except ValueError:
                pass
            if credit:
                self.credits_used += credit

            if 200 <= resp.status_code < 300:
                raw_path = self._record_raw(tool, method, path, h, body, resp, resp_body, retrieved)
                run = self._log(tool, method, path, h, body, "ok", http_status=resp.status_code, attempt=attempt,
                                t0=t0, credit=credit, resp_body=resp_body, raw_path=raw_path)
                res = CallResult(True, resp.status_code, resp_body, run, retrieved_at=retrieved)
                self._cache[h] = res
                return res

            et, msg = _error_info(resp.status_code, resp_body)
            run = self._log(tool, method, path, h, body, "error", http_status=resp.status_code, attempt=attempt,
                            t0=t0, credit=credit, resp_body=resp_body, error_type=et)
            res = CallResult(False, resp.status_code, resp_body, run, et, msg, retrieved)
            retryable = resp.status_code == 429 or resp.status_code >= 500
            if not retryable:
                break  # 4xx incl. 402 insufficient credits: retrying cannot help
            if attempt < max_attempts:
                self._sleep(self._delay(attempt, resp.headers.get("retry-after")))

        assert res is not None
        self.warnings.append(f"{tool} failed: {res.error_type} {res.message or ''}".strip())
        return res

    # ---- endpoint helpers (shapes verified in docs/crustdata_schema_notes.md) ----
    def credits(self) -> CallResult:
        return self.request("account_credits", "GET", "/account/credits")

    def company_search(self, filters: dict, fields: Iterable[str] | None = None, limit: int = 20,
                       cursor: str | None = None, sorts: list[dict] | None = None,
                       search: dict | None = None) -> CallResult:
        """`search` = {"query", "mode"} adds relevance ranking inside the filters (verified live; total_count is then
        null and sorts are not allowed)."""
        body: dict[str, Any] = {"filters": filters, "limit": limit}
        if search:
            body["search"] = search
        if fields:
            body["fields"] = list(fields)
        if cursor:
            body["cursor"] = cursor
        if sorts:
            body["sorts"] = sorts
        return self.request("company_search", "POST", "/company/search", body)

    def autocomplete(self, field: str, query: str, limit: int = 15) -> list[str]:
        """Free. Valid filter values for a company field; [] on any failure (caller decides what that means)."""
        r = self.request("company_autocomplete", "POST", "/company/search/autocomplete",
                         {"field": field, "query": query, "limit": limit})
        if not r.ok or not isinstance(r.body, dict):
            return []
        return [s["value"] for s in r.body.get("suggestions", []) if isinstance(s, dict) and isinstance(s.get("value"), str)]

    def company_search_paged(self, filters: dict, fields: Iterable[str] | None = None,
                             max_results: int | None = None, sorts: list[dict] | None = None,
                             search: dict | None = None) -> tuple[list[dict], int | None, str | None]:
        """Follow next_cursor up to max_results. Returns (companies, total_count, warning).
        Partial pages are preserved if a later page fails. `search_pages` records (raw_path, retrieved_at, first_index)
        per page so each record can cite the response file it came from."""
        cap = max_results or self.s.max_company_search_results
        out: list[dict] = []
        total: int | None = None
        cursor: str | None = None
        self.search_pages = []
        while len(out) < cap:
            r = self.company_search(filters, fields, min(self.s.search_page_size, cap - len(out)), cursor, sorts, search)
            if not r.ok:
                return out, total, f"company_search page failed after {len(out)} results: {r.error_type}"
            tc = r.body.get("total_count")
            total = tc if isinstance(tc, int) else total
            self.search_pages.append((r.run.raw_path, r.retrieved_at, len(out)))
            out.extend(r.body.get("companies") or [])
            cursor = r.body.get("next_cursor")
            if not cursor:
                break
        return out[:cap], total, None

    def _one_id(self, domains, names, ids, urls) -> dict[str, list]:
        given = {k: list(v) for k, v in (("domains", domains), ("names", names),
                 ("crustdata_company_ids", ids), ("professional_network_profile_urls", urls)) if v}
        if len(given) != 1:
            raise ValueError("exactly one identifier type is required")
        if len(next(iter(given.values()))) > 25:
            raise ValueError("max 25 identifiers per request")
        return given

    def company_identify(self, *, domains=None, names=None, ids=None, urls=None,
                         exact_match: bool | None = None) -> CallResult:
        body: dict[str, Any] = self._one_id(domains, names, ids, urls)
        if exact_match is not None:
            body["exact_match"] = exact_match
        return self.request("company_identify", "POST", "/company/identify", body)

    def company_enrich(self, *, domains=None, names=None, ids=None, urls=None,
                       fields: Iterable[str] = ("basic_info",), exact_match: bool | None = None) -> CallResult:
        body: dict[str, Any] = self._one_id(domains, names, ids, urls)
        body["fields"] = list(fields)
        if exact_match is not None:
            body["exact_match"] = exact_match
        return self.request("company_enrich", "POST", "/company/enrich", body)

    def company_ranked_search(self, query: str, fields: Iterable[str] | None = None, limit: int = 10,
                              mode: str = "hybrid") -> CallResult:
        """Ranked (relevance) search. total_count is always null for ranked search, per provider docs."""
        body: dict[str, Any] = {"search": {"query": query, "mode": mode}, "limit": limit}
        if fields:
            body["fields"] = list(fields)
        return self.request("competitor_search", "POST", "/company/search", body)

    def person_search(self, filters: dict, fields: Iterable[str] | None = None, limit: int = 10,
                      cursor: str | None = None, sorts: list[dict] | None = None) -> CallResult:
        body: dict[str, Any] = {"filters": filters, "limit": limit}
        if fields:
            body["fields"] = list(fields)
        if cursor:
            body["cursor"] = cursor
        if sorts:
            body["sorts"] = sorts
        return self.request("person_search", "POST", "/person/search", body)

    def web_search(self, query: str, location: str | None = None, sources: Iterable[str] = ("web",)) -> CallResult:
        body: dict[str, Any] = {"query": query, "sources": list(sources)}
        if location:
            body["location"] = location
        return self.request("web_search", "POST", "/web/search/live", body)

    def web_fetch(self, urls: list[str]) -> CallResult:
        return self.request("web_fetch", "POST", "/web/enrich/live", {"urls": urls[:10]})

    def close(self) -> None:
        self._http.close()
