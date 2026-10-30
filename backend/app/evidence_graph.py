"""Build a bounded, explainable evidence graph for an incident investigation."""
from __future__ import annotations
from typing import Any

def build_evidence_graph(hypotheses: list[dict[str, Any]], events: list[dict[str, Any]], deployments: list[dict[str, Any]], metric_signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Link citations and contextual observations without inventing causal claims."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    event_ids = {int(event["event_id"]) for event in events}
    for event in events:
        nodes.append({"id": f"event:{event['event_id']}", "type": "event", "timestamp": event.get("occurred_at"), "label": str(event.get("message", ""))[:240], "severity": event.get("severity")})
    deployment_ids = []
    for deployment in deployments:
        key = str(deployment.get("deployment_id", deployment.get("id", "unknown")))
        node_id = f"deployment:{key}"
        deployment_ids.append(node_id)
        nodes.append({"id": node_id, "type": "deployment", "timestamp": deployment.get("deployed_at"), "label": key, "outcome": deployment.get("outcome")})
    metric_ids = []
    for index, signal in enumerate(metric_signals):
        node_id = f"metric:{index}"
        metric_ids.append(node_id)
        nodes.append({"id": node_id, "type": "metric", "label": str(signal.get("query_name", "metric")), "latest_value": signal.get("latest_value"), "percent_change": signal.get("percent_change"), "sample_count": signal.get("sample_count")})
    assessments = []
    for index, hypothesis in enumerate(hypotheses):
        hypothesis_id = f"hypothesis:{index}"
        nodes.append({"id": hypothesis_id, "type": "hypothesis", "label": str(hypothesis.get("cause", "Hypothesis"))})
        cited = sorted({int(value) for value in hypothesis.get("evidence_event_ids", []) if int(value) in event_ids})
        for event_id in cited:
            edges.append({"source": f"event:{event_id}", "target": hypothesis_id, "relation": "supports_by_citation"})
        for node_id in deployment_ids:
            edges.append({"source": node_id, "target": hypothesis_id, "relation": "temporal_context"})
        for node_id in metric_ids:
            edges.append({"source": node_id, "target": hypothesis_id, "relation": "observational_context"})
        assessments.append({"hypothesis_id": hypothesis_id, "supporting_event_ids": cited, "contextual_evidence_ids": deployment_ids + metric_ids, "counter_evidence_ids": [], "counter_evidence_status": "not_evaluated", "assessment": "Citations and context are linked; contradictory evidence has not been inferred."})
    return {
        "version": "1.0", "nodes": nodes, "edges": edges, "hypothesis_assessments": assessments,
        "summary": {"event_count": len(events), "deployment_count": len(deployments), "metric_signal_count": len(metric_signals), "hypothesis_count": len(hypotheses), "edge_count": len(edges)},
        "limitations": [
            "A citation link means the investigator referenced that event; it does not prove causality.",
            "Deployment and metric links are contextual observations, not proof for or against a hypothesis.",
            "Counter-evidence is not inferred automatically; it requires explicit, validated diagnostic rules.",
        ],
    }
