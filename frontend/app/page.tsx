"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Incident = {
  id: number; title: string; service: string; environment: string;
  severity: "info" | "warning" | "error" | "critical";
  status: "open" | "investigating" | "resolved";
  first_seen: string; last_seen: string; event_count: number;
};
type ApiResult = { items: Incident[]; count: number };
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
        <div className="hero-note"><span className="note-icon">↳</span> This MVP uses deterministic, evidence-linked triage heuristics—not an LLM-generated root cause yet.</div>
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
            <span className="count-pill">{items.length} total</span>
          </div>
          {error && <div className="error-banner" role="alert">{error}</div>}
          {loading ? <div className="empty-state">Loading incident queue…</div> :
            items.length === 0 ? (
              <div className="empty-state"><div className="empty-symbol">⌁</div><strong>No incidents yet</strong><span>Send a sample event to create your first incident.</span></div>
            ) : (
              <div className="incident-list">
                {items.map((incident) => (
                  <article className="incident-row" key={incident.id}>
                    <div className={`severity-bar severity-${incident.severity}`} />
                    <div className="incident-main">
                      <div className="incident-title">{incident.title}</div>
                      <div className="incident-meta"><span>{incident.service}</span><span className="meta-dot">·</span><span>{incident.environment}</span><span className="meta-dot">·</span><span>{timeAgo(incident.last_seen)}</span></div>
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
