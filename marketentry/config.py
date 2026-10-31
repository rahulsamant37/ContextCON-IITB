"""Settings. Secrets come from the environment / .env only and are never printed or logged."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    crustdata_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    base_url: str = "https://api.crustdata.com"
    api_version: str = "2025-11-01"
    timeout_s: float = 60.0

    # modes
    replay: bool = False
    simulate_transient_failure: bool = False

    # retries / pacing (provider limit: 30 req/min)
    max_retries: int = 3
    backoff_base_s: float = 1.0
    backoff_max_s: float = 20.0
    min_interval_s: float = 2.0

    # cost caps
    max_credits_per_mission: float = 400.0
    max_company_search_results: int = 100
    max_company_enrichments: int = 10
    max_person_results: int = 10
    max_person_enrichments: int = 5
    max_web_queries: int = 6
    search_page_size: int = 50

    # paths
    fixtures_dir: Path = ROOT / "fixtures" / "raw"
    out_dir: Path = ROOT / "out"
    record_raw: bool = True

    # models (LLM = parsing + prose only)
    parse_model: str = "claude-haiku-5-5"
    prose_model: str = "claude-sonnet-5-5"

    def api_key(self) -> str | None:
        return self.crustdata_api_key.get_secret_value() if self.crustdata_api_key else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
