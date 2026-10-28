"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Incident = {
  id: number; title: string; service: string; environment: string;
  severity: "info" | "warning" | "error" | "critical";
  status: "open" | "investigating" | "resolved";
  first_seen: string; last_seen: string; event_count: number;
};
type Investigation = {
  method: string;
  summary: string;
  hypotheses: { cause: string; confidence: number; rationale: string; evidence_event_ids: number[]; next_checks: string[] }[];
  limitations: string[];
  metric_context?: {
    status: "available" | "not_configured" | "unavailable";
    query_count?: number;
    signals: { query_name: string; metric: Record<string, string>; sample_count: number; first_value: number; latest_value: number; absolute_change: number; percent_change: number | null; interpretation: string }[];
    limitations: string[];
  };
};
type ApiResult = { items: Incident[]; count: number };
type MetricContext = {
  source: string;
  window: { start: string; end: string; step_seconds: number };
  query_count: number;
  queries: { name: string; promql: string; result_type: string; series: { metric: Record<string, string>; values: [number, string][] }[]; series_count_returned: number }[];
  limitations: string[];
};
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function timeAgo(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function Home() {
  const [items, setItems] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("upstream request timeout after 30 seconds");
  const [investigations, setInvestigations] = useState<Record<number, Investigation>>({});
  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const [issueNotice, setIssueNotice] = useState<{ number: number; url: string } | null>(null);
  const [timelines, setTimelines] = useState<Record<number, { evidence: { event_id: number; occurred_at: string; service: string; severity: string; message: string; trace_id?: string | null; deployment_id?: string | null }[]; related_deployments: { id: number; deployment_id: string; version?: string | null; commit_sha?: string | null; actor?: string | null; outcome: string; deployed_at: string }[] }>>({});
  const [timelineBusy, setTimelineBusy] = useState<number | null>(null);
  const [metricBusy, setMetricBusy] = useState<number | null>(null);
  const [metricContexts, setMetricContexts] = useState<Record<number, MetricContext>>({});
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusBusy, setStatusBusy] = useState<number | null>(null);
  const filteredItems = items.filter((item) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || [item.title, item.service, item.environment, String(item.id)].some((value) => value.toLowerCase().includes(query));
    return matchesSearch && (statusFilter === "all" || item.status === statusFilter) && (severityFilter === "all" || item.severity === severityFilter);
  });

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/incidents?limit=100`, { cache: "no-store" });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const data = (await response.json()) as ApiResult;
      setItems(data.items);
      setError("");
    } catch {
      setError("Cannot reach the API. Start the backend at http://localhost:8000 and refresh.");
    } finally { setLoading(false); }
  }, []);

  // This effect starts an asynchronous fetch; state updates occur only after the API responds.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void refresh(); }, [refresh]);

  async function submitEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service: "checkout-api", environment: "demo", severity: "error",
          message, attributes: { source: "cloudops-demo" },
        }),
      });
      if (!response.ok) throw new Error((await response.text()) || "Event ingestion failed");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Event ingestion failed.");
    } finally { setBusy(false); }
  }

  async function runInvestigation(incidentId: number) {
    setActionBusy(incidentId);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/investigate`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Investigation failed.");
      setInvestigations((current) => ({ ...current, [incidentId]: body as Investigation }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Investigation failed.");
    } finally { setActionBusy(null); }
  }

  async function loadTimeline(incidentId: number) {
    setTimelineBusy(incidentId);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Could not load incident evidence.");
      setTimelines((current) => ({ ...current, [incidentId]: body }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load incident evidence.");
    } finally { setTimelineBusy(null); }
  }

  async function loadMetricContext(incidentId: number) {
    setMetricBusy(incidentId);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/metrics?lookback_minutes=30`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Could not load Prometheus metrics.");
      setMetricContexts((current) => ({ ...current, [incidentId]: body as MetricContext }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load Prometheus metrics.");
    } finally {
      setMetricBusy(null);
    }
  }

  async function updateStatus(incidentId: number, status: Incident["status"]) {
    setStatusBusy(incidentId);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Status update failed.");
      setItems((current) => current.map((item) => item.id === incidentId ? { ...item, status: body.status } : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Status update failed.");
    } finally {
      setStatusBusy(null);
    }
  }

  async function createIssue(incidentId: number) {
    setActionBusy(incidentId);
    setError("");
    setIssueNotice(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/github-issue`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "GitHub issue creation failed.");
      setIssueNotice({ number: body.issue_number, url: body.issue_url });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GitHub issue creation failed.");
    } finally { setActionBusy(null); }
  }

  const openCount = items.filter((item) => item.status === "open").length;
  const investigatingCount = items.filter((item) => item.status === "investigating").length;
  const criticalCount = items.filter((item) => item.severity === "critical").length;

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="CloudOps AI home">
          <span className="brand-mark">C</span><span>cloudops<span className="brand-muted">.ai</span></span>
        </Link>
        <div className="topbar-right"><span className="live-dot" /> LOCAL DEVELOPMENT</div>
      </header>

      <section className="hero">
        <div className="eyebrow"><span className="eyebrow-line" /> INCIDENT INTELLIGENCE</div>
        <h1>From noisy alerts<br /><span>to clear evidence.</span></h1>
        <p className="hero-copy">A focused workspace for correlating production signals, tracking incidents, and investigating what might have gone wrong.</p>
        <div className="hero-note"><span className="note-icon">↳</span> Evidence-linked triage with deterministic fallback and optional LLM hypotheses.</div>
      </section>

      <section className="metrics" aria-label="Incident summary">
        <Metric label="TOTAL INCIDENTS" value={String(items.length).padStart(2, "0")} detail="Recorded in local store" />
        <Metric label="OPEN" value={String(openCount).padStart(2, "0")} detail="Awaiting triage" />
        <Metric label="INVESTIGATING" value={String(investigatingCount).padStart(2, "0")} detail="Being investigated" />
        <Metric label="CRITICAL" value={String(criticalCount).padStart(2, "0")} detail="Highest severity" />
      </section>

      <section className="content-grid">
        <div className="panel incidents-panel">
          <div className="panel-heading">
            <div><div className="section-kicker">OPERATIONS</div><h2>Incident queue</h2></div>
            <span className="count-pill">{filteredItems.length} of {items.length}</span>
          </div>
          <div className="queue-tools">
            <div className="queue-search">
              <label htmlFor="incident-search">SEARCH INCIDENTS</label>
              <input id="incident-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title, service, environment, or ID…" />
            </div>
            <div className="queue-filter">
              <label htmlFor="status-filter">STATUS</label>
              <select id="status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option>
              </select>
            </div>
            <div className="queue-filter">
              <label htmlFor="severity-filter">SEVERITY</label>
              <select id="severity-filter" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
                <option value="all">All severities</option><option value="critical">Critical</option><option value="error">Error</option><option value="warning">Warning</option><option value="info">Info</option>
              </select>
            </div>
            {(search || statusFilter !== "all" || severityFilter !== "all") && <button className="text-button clear-filters" onClick={() => { setSearch(""); setStatusFilter("all"); setSeverityFilter("all"); }}>Clear filters</button>}
          </div>
          {error && <div className="error-banner" role="alert">{error}</div>}
          {issueNotice && <div className="success-banner">GitHub issue #{issueNotice.number} ready. <a href={issueNotice.url} target="_blank" rel="noreferrer">Open issue ↗</a></div>}
          {loading ? <div className="empty-state">Loading incident queue…</div> :
            filteredItems.length === 0 ? (
              <div className="empty-state"><div className="empty-symbol">⌁</div><strong>No incidents yet</strong><span>{items.length === 0 ? "Send a sample event to create your first incident." : "Try another search or clear your filters."}</span></div>
            ) : (
              <div className="incident-list">
                {filteredItems.map((incident) => (
                  <article className="incident-row" key={incident.id}>
                    <div className={`severity-bar severity-${incident.severity}`} />
                    <div className="incident-main">
                      <div className="incident-title">{incident.title}</div>
                      <div className="incident-meta"><span>{incident.service}</span><span className="meta-dot">·</span><span>{incident.environment}</span><span className="meta-dot">·</span><span>{timeAgo(incident.last_seen)}</span></div>
                      <div className="row-actions">
                        <button className="mini-button" onClick={() => void runInvestigation(incident.id)} disabled={actionBusy !== null}>{actionBusy === incident.id ? "Working…" : "Investigate"}</button>
                        <button className="mini-button mini-button-secondary" onClick={() => void loadTimeline(incident.id)} disabled={timelineBusy !== null}>{timelineBusy === incident.id ? "Loading…" : timelines[incident.id] ? "Refresh timeline" : "Evidence timeline"}</button>
                        <button className="mini-button mini-button-secondary" onClick={() => void loadMetricContext(incident.id)} disabled={metricBusy !== null}>{metricBusy === incident.id ? "Querying…" : metricContexts[incident.id] ? "Refresh metrics" : "Metric context"}</button>
                        <button className="mini-button mini-button-secondary" onClick={() => void createIssue(incident.id)} disabled={actionBusy !== null}>Create GitHub issue</button>
                        {incident.status !== "investigating" && incident.status !== "resolved" && <button className="mini-button mini-button-secondary" onClick={() => void updateStatus(incident.id, "investigating")} disabled={statusBusy !== null}>{statusBusy === incident.id ? "Saving…" : "Mark investigating"}</button>}
                        {incident.status !== "resolved" && <button className="mini-button mini-button-resolve" onClick={() => void updateStatus(incident.id, "resolved")} disabled={statusBusy !== null}>{statusBusy === incident.id ? "Saving…" : "Resolve incident"}</button>}
                        {incident.status === "resolved" && <button className="mini-button mini-button-secondary" onClick={() => void updateStatus(incident.id, "open")} disabled={statusBusy !== null}>{statusBusy === incident.id ? "Saving…" : "Reopen incident"}</button>}
                      </div>
                      {timelines[incident.id] && (
                        <div className="timeline-result">
                          <div className="investigation-heading">EVENT EVIDENCE TIMELINE · {timelines[incident.id].evidence.length} records</div>
                          {timelines[incident.id].evidence.map((item) => (
                            <div className="timeline-event" key={item.event_id}>
                              <span className="timeline-time">{new Date(item.occurred_at).toLocaleString()}</span>
                              <span className={`severity-tag severity-tag-${item.severity}`}>{item.severity}</span>
                              <p>{item.message}</p>
                              <div className="timeline-meta">Event #{item.event_id}{item.trace_id ? ` · trace ${item.trace_id}` : ""}{item.deployment_id ? ` · deployment ${item.deployment_id}` : ""}</div>
                            </div>
                          ))}
                          {timelines[incident.id].related_deployments.length > 0 && (
                            <div className="deployment-context">
                              <div className="investigation-heading">NEARBY DEPLOYMENTS · temporal context, not proof of cause</div>
                              {timelines[incident.id].related_deployments.map((deployment) => (
                                <div className="deployment-event" key={deployment.id}>
                                  <strong>{deployment.deployment_id}</strong>
                                  <span className="hypothesis-score">{deployment.outcome} · {new Date(deployment.deployed_at).toLocaleString()}</span>
                                  <div className="timeline-meta">{deployment.version ? `version ${deployment.version}` : "version not supplied"}{deployment.commit_sha ? ` · commit ${deployment.commit_sha}` : ""}{deployment.actor ? ` · by ${deployment.actor}` : ""}</div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      {metricContexts[incident.id] && (
                        <div className="timeline-result">
                          <div className="investigation-heading">PROMETHEUS METRIC CONTEXT · {metricContexts[incident.id].query_count} QUERIES</div>
                          <div className="timeline-meta">{new Date(metricContexts[incident.id].window.start).toLocaleString()} – {new Date(metricContexts[incident.id].window.end).toLocaleString()} · {metricContexts[incident.id].window.step_seconds}s step</div>
                          {metricContexts[incident.id].queries.map((query) => (
                            <div className="deployment-event" key={query.name}>
                              <strong>{query.name}</strong>
                              <span className="hypothesis-score">{query.series_count_returned} series · {query.result_type}</span>
                              <code className="metric-query">{query.promql}</code>
                              {query.series.map((series, seriesIndex) => (
                                <div className="timeline-meta" key={query.name + "-" + seriesIndex}>
                                  {Object.entries(series.metric).map(([key, value]) => key + "=" + value).join(" · ") || "Unlabelled series"}
                                  {" · "}{series.values.length} samples
                                  {series.values.length > 0 ? " · latest " + series.values[series.values.length - 1][1] : " · no samples"}
                                </div>
                              ))}
                            </div>
                          ))}
                          {metricContexts[incident.id].limitations.map((limitation) => <div className="limitation" key={limitation}>{limitation}</div>)}
                        </div>
                      )}
                      {investigations[incident.id] && (
                        <div className="investigation-result">
                          <div className="investigation-heading">{investigations[incident.id].method}</div>
                          <p>{investigations[incident.id].summary}</p>
                          {investigations[incident.id].hypotheses.map((hypothesis, index) => (
                            <div className="hypothesis" key={`${incident.id}-${index}`}>
                              <strong>{hypothesis.cause}</strong>
                              <span className="hypothesis-score">score {hypothesis.confidence.toFixed(2)} · evidence {hypothesis.evidence_event_ids.map((id) => `#${id}`).join(", ")}</span>
                              <p>{hypothesis.rationale}</p>
                              <ul>{hypothesis.next_checks.map((check) => <li key={check}>{check}</li>)}</ul>
                            </div>
                          ))}
                          {investigations[incident.id].limitations.map((limitation) => <div className="limitation" key={limitation}>{limitation}</div>)}
                          {investigations[incident.id].metric_context && (
                            <div className="investigation-metrics">
                              <div className="investigation-heading">LIVE METRIC EVIDENCE · {investigations[incident.id].metric_context.status.replace("_", " ").toUpperCase()}</div>
                              {investigations[incident.id].metric_context.signals.map((signal, signalIndex) => (
                                <div className="metric-signal" key={signal.query_name + "-" + signalIndex}>
                                  <strong>{signal.query_name}</strong>
                                  <span>{Object.entries(signal.metric).map(([key, value]) => key + "=" + value).join(" · ") || "Unlabelled series"}</span>
                                  <span>{signal.first_value} → {signal.latest_value}{signal.percent_change !== null ? " · " + signal.percent_change + "% change" : " · baseline is zero"}</span>
                                  <small>{signal.interpretation}</small>
                                </div>
                              ))}
                              {investigations[incident.id].metric_context.signals.length === 0 && <p className="limitation">No numeric metric samples were available to summarize.</p>}
                              {investigations[incident.id].metric_context.limitations.map((limitation) => <div className="limitation" key={limitation}>{limitation}</div>)}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="incident-right">
                      <span className={`severity-tag severity-tag-${incident.severity}`}>{incident.severity}</span>
                      <span className={`status-tag status-${incident.status}`}>{incident.status}</span>
                      <span className="event-count">{incident.event_count} event{incident.event_count === 1 ? "" : "s"}</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          <div className="panel-footer"><span>Updates on refresh</span><button className="text-button" onClick={() => void refresh()}>↻ Refresh queue</button></div>
        </div>

        <aside className="panel demo-panel">
          <div className="section-kicker">INTERACTIVE DEMO</div><h2>Trigger a signal</h2>
          <p className="panel-copy">Send a sample application event into the API. Repeated, similar messages from the same service are grouped into one incident inside the correlation window.</p>
          <form onSubmit={submitEvent}>
            <label htmlFor="event-message">EVENT MESSAGE</label>
            <textarea id="event-message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={8000} required />
            <div className="form-meta"><span>Service: <strong>checkout-api</strong></span><span>Environment: <strong>demo</strong></span></div>
            <button className="primary-button" type="submit" disabled={busy || !message.trim()}>{busy ? "Sending event…" : "＋  Ingest sample event"}</button>
          </form>
          <div className="demo-tip"><span>TIP</span> Send the same message twice to see event correlation increase the incident count.</div>
        </aside>
      </section>
      <footer className="footer"><span>CloudOps AI <span className="footer-muted">/ Early-stage engineering preview</span></span><span>Evidence first. Certainty earned.</span></footer>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="metric-card"><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail">{detail}</div></div>;
}
