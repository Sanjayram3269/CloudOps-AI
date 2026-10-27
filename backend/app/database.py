"""Small SQLite persistence layer for the local MVP."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from backend.app.config import database_path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a transaction-scoped connection and always close it."""
    path = Path(database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                service TEXT NOT NULL,
                environment TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                fingerprint TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 1,
                github_issue_url TEXT,
                github_issue_number INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_incidents_last_seen
                ON incidents(last_seen DESC);
            CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint
                ON incidents(service, environment, fingerprint, last_seen);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                service TEXT NOT NULL,
                environment TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                trace_id TEXT,
                deployment_id TEXT,
                attributes_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_events_incident_time
                ON events(incident_id, occurred_at DESC);
            """
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(incidents)")}
        if "github_issue_url" not in columns:
            db.execute("ALTER TABLE incidents ADD COLUMN github_issue_url TEXT")
        if "github_issue_number" not in columns:
            db.execute("ALTER TABLE incidents ADD COLUMN github_issue_number INTEGER")


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_incident(incident_id: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return row_dict(row)


def list_incidents(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM incidents ORDER BY last_seen DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_events(incident_id: int) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT id AS event_id, occurred_at, service, severity, message,
                      trace_id, deployment_id
               FROM events WHERE incident_id = ?
               ORDER BY occurred_at DESC, id DESC""",
            (incident_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def ingest_event(event: dict[str, Any], fingerprint: str, window_seconds: int) -> tuple[int, int, bool]:
    """Persist an event and group it with a recent matching incident when possible."""
    occurred_at = event["occurred_at"]
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            """SELECT * FROM incidents
               WHERE service = ? AND environment = ? AND fingerprint = ?
                 AND status != 'resolved'
                 AND ABS(strftime('%s', ?) - strftime('%s', last_seen)) <= ?
               ORDER BY last_seen DESC LIMIT 1""",
            (
                event["service"], event["environment"], fingerprint,
                occurred_at, window_seconds,
            ),
        ).fetchone()

        grouped = existing is not None
        if existing:
            incident_id = int(existing["id"])
            severity_order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
            severity = max(
                (existing["severity"], event["severity"]),
                key=lambda value: severity_order.get(value, 0),
            )
            first_seen = min(existing["first_seen"], occurred_at)
            last_seen = max(existing["last_seen"], occurred_at)
            db.execute(
                """UPDATE incidents SET severity = ?, first_seen = ?, last_seen = ?,
                   event_count = event_count + 1 WHERE id = ?""",
                (severity, first_seen, last_seen, incident_id),
            )
        else:
            title = f'{event["service"]}: {event["message"][:96]}'
            cursor = db.execute(
                """INSERT INTO incidents
                   (title, service, environment, severity, status, fingerprint,
                    first_seen, last_seen, event_count)
                   VALUES (?, ?, ?, ?, 'open', ?, ?, ?, 1)""",
                (
                    title, event["service"], event["environment"], event["severity"],
                    fingerprint, occurred_at, occurred_at,
                ),
            )
            incident_id = int(cursor.lastrowid)

        cursor = db.execute(
            """INSERT INTO events
               (incident_id, service, environment, severity, message, occurred_at,
                trace_id, deployment_id, attributes_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                incident_id, event["service"], event["environment"], event["severity"],
                event["message"], occurred_at, event.get("trace_id"),
                event.get("deployment_id"),
                json.dumps(event.get("attributes", {}), sort_keys=True),
            ),
        )
        event_id = int(cursor.lastrowid)
        db.commit()
        return event_id, incident_id, grouped


def update_incident_status(incident_id: int, status: str) -> dict[str, Any] | None:
    with connect() as db:
        cursor = db.execute(
            "UPDATE incidents SET status = ? WHERE id = ?", (status, incident_id)
        )
        if cursor.rowcount == 0:
            return None
        row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return row_dict(row)



def save_github_issue(incident_id: int, url: str, number: int) -> dict[str, Any] | None:
    """Persist a GitHub issue reference once; repeated requests reuse the stored issue."""
    with connect() as db:
        db.execute(
            """UPDATE incidents SET github_issue_url = ?, github_issue_number = ?
               WHERE id = ? AND github_issue_url IS NULL""",
            (url, number, incident_id),
        )
        row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return row_dict(row)
