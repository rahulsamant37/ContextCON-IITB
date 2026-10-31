"""Local SQLite CRM. Idempotent: every row has a natural unique key, writes are upserts, and per-mission logs
(evidence, tool_runs) are replaced atomically. Outreach lives only here as unsent drafts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .contracts import CompanyRecord, Evidence, MarketBrief, PersonRecord, ToolRun
from .evidence import utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  id TEXT PRIMARY KEY, raw_prompt TEXT, normalized_brief_json TEXT, status TEXT,
  started_at TEXT, finished_at TEXT, warnings_json TEXT);
CREATE TABLE IF NOT EXISTS segments(
  id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
  UNIQUE(mission_id, name));
CREATE TABLE IF NOT EXISTS companies(
  id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, account_key TEXT NOT NULL,
  crustdata_company_id TEXT, name TEXT, domain TEXT, normalized_json TEXT,
  fit_score REAL, coverage_score REAL, verification_status TEXT,
  segment TEXT, stage TEXT NOT NULL DEFAULT 'New', updated_at TEXT,
  UNIQUE(mission_id, account_key));
CREATE TABLE IF NOT EXISTS people(
  id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, person_key TEXT NOT NULL,
  crustdata_person_id TEXT, company_id INTEGER REFERENCES companies(id), name TEXT, title TEXT,
  normalized_json TEXT, verified_employment INTEGER, UNIQUE(mission_id, person_key));
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, evidence_id TEXT NOT NULL, subject_id TEXT, claim TEXT,
  source_type TEXT, source_pointer TEXT, field_path TEXT, retrieved_at TEXT, status TEXT,
  UNIQUE(mission_id, evidence_id));
CREATE TABLE IF NOT EXISTS tool_runs(
  id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, run_id TEXT NOT NULL, tool_name TEXT, endpoint TEXT,
  request_hash TEXT, request_summary TEXT, result_status TEXT, http_status INTEGER, attempt INTEGER,
  duration_ms INTEGER, credit_cost REAL, error_type TEXT, started_at TEXT, UNIQUE(mission_id, run_id));
CREATE TABLE IF NOT EXISTS crm_tasks(
  id INTEGER PRIMARY KEY, mission_id TEXT NOT NULL, task_key TEXT NOT NULL, company_id INTEGER REFERENCES companies(id),
  task_type TEXT, title TEXT, status TEXT, draft_text TEXT, UNIQUE(mission_id, task_key));
"""


def mission_id_for(brief: MarketBrief) -> str:
    """Deterministic: the same normalized brief always maps to the same mission, so re-runs upsert."""
    core = brief.model_dump(exclude={"raw_prompt", "assumptions"})
    return "mission_" + hashlib.sha1(json.dumps(core, sort_keys=True).encode()).hexdigest()[:10]


def account_key(rec: CompanyRecord) -> str:
    if rec.company_id:
        return f"id:{rec.company_id}"
    if rec.domain:
        return f"domain:{rec.domain.lower()}"
    return f"name:{rec.name.strip().lower()}"


def person_key(rec: PersonRecord) -> str:
    return f"id:{rec.person_id}" if rec.person_id else f"co:{rec.company_id}|{rec.name.strip().lower()}"


class CRM:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def close(self) -> None:
        self.db.close()

    # ---- writes (all idempotent) --------------------------------------------
    def upsert_mission(self, mission_id: str, raw_prompt: str, brief: MarketBrief | None, status: str,
                       started_at: str | None = None, finished_at: str | None = None,
                       warnings: Iterable[str] = ()) -> None:
        with self.tx() as db:
            db.execute(
                """INSERT INTO missions(id, raw_prompt, normalized_brief_json, status, started_at, finished_at, warnings_json)
                   VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET raw_prompt=excluded.raw_prompt,
                   normalized_brief_json=excluded.normalized_brief_json, status=excluded.status,
                   started_at=excluded.started_at, finished_at=excluded.finished_at, warnings_json=excluded.warnings_json""",
                (mission_id, raw_prompt, brief.model_dump_json() if brief else None, status,
                 started_at or utcnow(), finished_at, json.dumps(list(warnings))))

    def upsert_company(self, mission_id: str, rec: CompanyRecord) -> int:
        """Stage is preserved on update so manual CRM progress is never overwritten by a re-run."""
        with self.tx() as db:
            db.execute(
                """INSERT INTO companies(mission_id, account_key, crustdata_company_id, name, domain, normalized_json,
                   fit_score, coverage_score, verification_status, segment, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(mission_id, account_key) DO UPDATE SET crustdata_company_id=excluded.crustdata_company_id,
                   name=excluded.name, domain=excluded.domain, normalized_json=excluded.normalized_json,
                   fit_score=excluded.fit_score, coverage_score=excluded.coverage_score,
                   verification_status=excluded.verification_status, segment=excluded.segment, updated_at=excluded.updated_at""",
                (mission_id, account_key(rec), rec.company_id, rec.name, rec.domain, rec.model_dump_json(), rec.fit_score,
                 rec.data_coverage, rec.verification_status, rec.wave, utcnow()))
        return self.db.execute("SELECT id FROM companies WHERE mission_id=? AND account_key=?",
                               (mission_id, account_key(rec))).fetchone()["id"]

    def upsert_person(self, mission_id: str, rec: PersonRecord, company_row_id: int | None) -> int:
        with self.tx() as db:
            db.execute(
                """INSERT INTO people(mission_id, person_key, crustdata_person_id, company_id, name, title, normalized_json,
                   verified_employment) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(mission_id, person_key) DO UPDATE SET
                   company_id=excluded.company_id, name=excluded.name, title=excluded.title,
                   normalized_json=excluded.normalized_json, verified_employment=excluded.verified_employment""",
                (mission_id, person_key(rec), rec.person_id, company_row_id, rec.name, rec.current_title,
                 rec.model_dump_json(), int(rec.employer_verified)))
        return self.db.execute("SELECT id FROM people WHERE mission_id=? AND person_key=?",
                               (mission_id, person_key(rec))).fetchone()["id"]

    def upsert_task(self, mission_id: str, task_key: str, company_row_id: int | None, task_type: str, title: str,
                    status: str, draft_text: str | None = None) -> None:
        """Existing task status is kept (a human may have progressed it); title/draft are refreshed."""
        with self.tx() as db:
            db.execute(
                """INSERT INTO crm_tasks(mission_id, task_key, company_id, task_type, title, status, draft_text)
                   VALUES(?,?,?,?,?,?,?) ON CONFLICT(mission_id, task_key) DO UPDATE SET company_id=excluded.company_id,
                   task_type=excluded.task_type, title=excluded.title, draft_text=excluded.draft_text""",
                (mission_id, task_key, company_row_id, task_type, title, status, draft_text))

    def replace_evidence(self, mission_id: str, items: Iterable[Evidence]) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM evidence WHERE mission_id=?", (mission_id,))
            db.executemany(
                """INSERT INTO evidence(mission_id, evidence_id, subject_id, claim, source_type, source_pointer, field_path,
                   retrieved_at, status) VALUES(?,?,?,?,?,?,?,?,?)""",
                [(mission_id, e.evidence_id, e.subject_id, e.claim, e.source_kind, e.raw_ref or e.source_url,
                  e.field_path, e.retrieved_at_utc, e.status) for e in items])

    def replace_tool_runs(self, mission_id: str, runs: Iterable[ToolRun]) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM tool_runs WHERE mission_id=?", (mission_id,))
            db.executemany(
                """INSERT INTO tool_runs(mission_id, run_id, tool_name, endpoint, request_hash, request_summary, result_status,
                   http_status, attempt, duration_ms, credit_cost, error_type, started_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(mission_id, r.run_id, r.tool_name, r.endpoint, r.request_hash, r.request_summary, r.result_status,
                  r.http_status, r.attempt, r.duration_ms, r.credit_cost, r.error_type, r.started_at_utc) for r in runs])

    def sync_segments(self, mission_id: str) -> None:
        desc = {"Wave 1": "High fit, verified buyer: launch first", "Wave 2": "Fit confirmed, buyer/data pending",
                "Research Needed": "Insufficient evidence or identity: complete research before outreach"}
        with self.tx() as db:
            for name, d in desc.items():
                db.execute("INSERT INTO segments(mission_id, name, description) VALUES(?,?,?) "
                           "ON CONFLICT(mission_id, name) DO UPDATE SET description=excluded.description", (mission_id, name, d))

    # ---- reads ---------------------------------------------------------------
    def counts(self, mission_id: str) -> dict[str, int]:
        out = {}
        for t in ("companies", "people", "evidence", "tool_runs", "crm_tasks", "segments"):
            out[t] = self.db.execute(f"SELECT COUNT(*) c FROM {t} WHERE mission_id=?", (mission_id,)).fetchone()["c"]
        out["unsent_drafts"] = self.db.execute(
            "SELECT COUNT(*) c FROM crm_tasks WHERE mission_id=? AND status='draft_unsent'", (mission_id,)).fetchone()["c"]
        return out

    def rows(self, table: str, mission_id: str) -> list[dict]:
        if table not in {"missions", "segments", "companies", "people", "evidence", "tool_runs", "crm_tasks"}:
            raise ValueError(table)
        col = "id" if table == "missions" else "mission_id"
        return [dict(r) for r in self.db.execute(f"SELECT * FROM {table} WHERE {col}=? ORDER BY id", (mission_id,))]
