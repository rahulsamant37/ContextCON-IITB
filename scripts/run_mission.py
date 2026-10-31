"""CLI: python scripts/run_mission.py "<prompt>"   (REPLAY=1 / SIMULATE_TRANSIENT_FAILURE=1 honoured via env)"""
from __future__ import annotations

import sys

from marketentry.orchestrator import run_mission


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = run_mission(" ".join(sys.argv[1:]), on_event=lambda e: print(f"[{e['step']}] {e['msg']}"
                    + (f"  credit={e['credit']}" if e.get("credit") is not None else "")))
    r = d.result()
    print(f"\nstate={r.state} mission={r.mission_id} credits={r.credit_used}")
    print(f"universe: indexed={r.universe.total_count} fetched={r.universe.fetched}")
    print(r.sizing.formula_text)
    for c in d.companies[:10]:
        print(f"  {c.fit_score!s:>5} cov={c.data_coverage:.2f} {c.wave!s:<16} {c.name} ({c.domain}) hc={c.employee_count} "
              f"g6={c.headcount_growth_6m} roles={c.open_roles} enriched={c.enriched}")
    print("crm:", r.crm_counts)
    for w in r.warnings:
        print("WARN:", w)


if __name__ == "__main__":
    main()
