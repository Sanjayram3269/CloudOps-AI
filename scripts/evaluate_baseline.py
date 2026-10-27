"""Run a deterministic, labelled regression suite for the baseline investigator."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.app.investigation import investigate  # noqa: E402

def evaluate(dataset_path: Path) -> dict[str, Any]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = []
    top1_hits = top3_hits = 0
    for index, case in enumerate(dataset["cases"], start=1):
        timestamp = "2026-01-01T00:00:00+00:00"
        event = {"event_id": index, "occurred_at": timestamp, "service": case["service"],
                 "severity": "error", "message": case["message"], "trace_id": None,
                 "deployment_id": None}
        incident = {"id": index, "title": f"{case['service']}: seeded evaluation case",
                    "service": case["service"], "environment": "evaluation", "severity": "error",
                    "status": "open", "first_seen": timestamp, "last_seen": timestamp}
        output = investigate(incident, [event])
        ranked = [item["cause"] for item in output["hypotheses"]]
        top1 = bool(ranked and ranked[0] == case["expected_cause"])
        top3 = case["expected_cause"] in ranked[:3]
        top1_hits += int(top1)
        top3_hits += int(top3)
        results.append({"case_id": case["id"], "expected_cause": case["expected_cause"],
                        "ranked_causes": ranked, "top1_correct": top1, "top3_correct": top3})
    total = len(results)
    return {"dataset": dataset["dataset"], "dataset_version": dataset["version"],
            "evaluation_type": "synthetic deterministic-rule regression; not production RCA accuracy",
            "cases": total, "top1_accuracy": round(top1_hits / total, 4) if total else 0.0,
            "top3_accuracy": round(top3_hits / total, 4) if total else 0.0, "results": results}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "samples" / "incident-evaluation.json")
    parser.add_argument("--output", type=Path, help="Optional path for a JSON report")
    parser.add_argument("--min-top1", type=float, default=None, help="Optional regression gate from 0 to 1")
    args = parser.parse_args()
    if args.min_top1 is not None and not 0 <= args.min_top1 <= 1:
        parser.error("--min-top1 must be between 0 and 1")
    report = evaluate(args.dataset)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 1 if args.min_top1 is not None and report["top1_accuracy"] < args.min_top1 else 0

if __name__ == "__main__":
    raise SystemExit(main())
