"""T0 probe: hit each Crustdata endpoint with tiny requests and save raw responses to fixtures/raw/.

Usage: python scripts/probe_crustdata.py <step> [args...]
Steps are run one at a time so each request is derived from the previous saved response.
The API key is read from env / .env and is never written to disk.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "fixtures" / "raw"
BASE = "https://api.crustdata.com"
KEEP_HEADERS = ("x-credits-used", "retry-after", "content-type")


def call(name: str, method: str, path: str, body: dict | None = None) -> dict:
    load_dotenv(ROOT / ".env")
    key = os.environ["CRUSTDATA_API_KEY"]
    headers = {
        "Authorization": f"Bearer {key}",
        "x-api-version": "2025-11-01",
        "Content-Type": "application/json",
    }
    t0 = time.time()
    r = httpx.request(method, BASE + path, headers=headers, json=body, timeout=60)
    try:
        payload = r.json()
    except Exception:
        payload = {"_non_json_body": r.text[:2000]}
    rec = {
        "name": name,
        "endpoint": f"{method} {path}",
        "request": body,
        "http_status": r.status_code,
        "response_headers": {
            k: v for k, v in r.headers.items()
            if k.lower() in KEEP_HEADERS or k.lower().startswith("x-ratelimit")
        },
        "duration_ms": int((time.time() - t0) * 1000),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "body": payload,
    }
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{name}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    print(f"[{name}] {rec['endpoint']} -> {r.status_code} credits={rec['response_headers'].get('x-credits-used')} ({rec['duration_ms']}ms)")
    return rec


def show(rec: dict, limit: int = 1800) -> None:
    print(json.dumps(rec["body"], indent=1, ensure_ascii=False)[:limit])


if __name__ == "__main__":
    step, args = sys.argv[1], sys.argv[2:]
    if step == "credits":
        show(call("account_credits", "GET", "/account/credits"))
    elif step == "autocomplete":  # field query
        rec = call(f"autocomplete_{args[0].replace('.', '_')}_{args[1] or 'all'}", "POST",
                   "/company/search/autocomplete", {"field": args[0], "query": args[1], "limit": 15})
        show(rec)
    elif step == "raw":  # name method path json-body
        show(call(args[0], args[1], args[2], json.loads(args[3]) if len(args) > 3 else None), 4000)
    else:
        sys.exit(f"unknown step {step}")
