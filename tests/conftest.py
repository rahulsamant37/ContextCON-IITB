import json
from pathlib import Path

import pytest

from marketentry.config import Settings

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "raw"


def fixture(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, crustdata_api_key="test-secret-key-123", out_dir=tmp_path,
                    fixtures_dir=FIX, min_interval_s=0.0, backoff_base_s=0.01, backoff_max_s=0.05,
                    replay=False, simulate_transient_failure=False)
