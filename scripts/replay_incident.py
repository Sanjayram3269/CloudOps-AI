"""Replay an incident as of a timestamp without exposing future events."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.app.investigation import investigate  # noqa: E402

def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed

def replay(scenario_path: Path) -> dict[str, Any]:
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    cutoff = _parse_time(scenario["as_of"])
    events = scenario["events"]
    visible = [item for item in events if _parse_time(item["occurred_at"]) <= cutoff]
    withheld = [item for item in events if _parse_time(item["occurred_at"]) > cutoff]
    incident = dict(scenario["incident"])
    incident["first_seen"] = min((item["occurred_at"] for item in visible), default=scenario["as_of"])
    incident["last_seen"] = max((item["occurred_at"] for item in visible), default=scenario["as_of"])
    result = investigate(incident, visible, allow_llm=False)
    visible_ids = {int(item["event_id"]) for item in visible}
    returned_ids = {
        int(value)
        for hypothesis in result.get("hypotheses", [])
        for value in hypothesis.get("evidence_event_ids", [])
    }
    evidence_ids = {int(item["event_id"]) for item in result.get("evidence", [])}
    leaked = sorted((returned_ids | evidence_ids) - visible_ids)
    expected = scenario.get("expected_cause")
    ranked = [item["cause"] for item in result.get("hypotheses", [])]
    return {
        "scenario_id": scenario["scenario_id"],
        "as_of": scenario["as_of"],
        "visible_event_ids": sorted(visible_ids),
        "withheld_future_event_ids": sorted(int(item["event_id"]) for item in withheld),
        "investigation_evidence_ids": sorted(evidence_ids),
        "hypotheses": result.get("hypotheses", []),
        "expected_cause": expected,
        "top1_correct": bool(ranked and expected and ranked[0] == expected),
        "future_leakage_detected": bool(leaked),
        "leaked_event_ids": leaked,
        "evaluation_note": "One synthetic temporal replay fixture; this is a leakage regression check, not a production RCA accuracy metric."
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "samples" / "replay-scenario.json")
    parser.add_argument("--output", type=Path, help="Optional path for a JSON report")
    args = parser.parse_args()
    report = replay(args.scenario)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 1 if report["future_leakage_detected"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
