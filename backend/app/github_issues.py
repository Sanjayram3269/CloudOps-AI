"""Optional GitHub issue creation with incident marker reuse and basic redaction."""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

from backend.app import database


_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|password|secret|authorization)\s*[:=]\s*[^\s,;]+"
)


class GitHubIssueConfigurationError(RuntimeError):
    pass


class GitHubIssueError(RuntimeError):
    pass


def redact_message(value: str) -> str:
    return _SECRET_RE.sub(r"\1=[REDACTED]", value[:1200])


def create_or_get_github_issue(
    incident: dict[str, Any], investigation: dict[str, Any]
) -> dict[str, Any]:
    existing_url = incident.get("github_issue_url")
    if existing_url:
        return {
            "issue_url": existing_url,
            "issue_number": incident.get("github_issue_number"),
            "reused": True,
        }

    token = os.getenv("GITHUB_TOKEN", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not token or not repository:
        raise GitHubIssueConfigurationError(
            "Configure GITHUB_TOKEN and GITHUB_REPOSITORY to enable issue creation"
        )
    if not _REPO_RE.fullmatch(repository):
        raise GitHubIssueConfigurationError("GITHUB_REPOSITORY must use owner/repository format")

    marker = f"<!-- cloudops-incident:{int(incident['id'])} -->"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_url = f"https://api.github.com/repos/{repository}"
    try:
        with httpx.Client(headers=headers, timeout=15.0) as client:
            lookup = client.get(f"{base_url}/issues", params={"state": "all", "per_page": 100})
            if lookup.is_error:
                raise GitHubIssueError("Unable to check for an existing incident issue")
            for issue in lookup.json():
                if "pull_request" not in issue and marker in (issue.get("body") or ""):
                    saved = database.save_github_issue(
                        int(incident["id"]), issue["html_url"], int(issue["number"])
                    )
                    return {
                        "issue_url": saved["github_issue_url"] if saved else issue["html_url"],
                        "issue_number": saved["github_issue_number"] if saved else issue["number"],
                        "reused": True,
                    }

            evidence_lines = []
            for item in investigation.get("evidence", [])[:20]:
                evidence_lines.append(
                    f"- Event #{item.get('event_id')} | {item.get('occurred_at')} | "
                    f"{item.get('severity')} | {redact_message(str(item.get('message', '')))}"
                )
            hypothesis_lines = []
            for item in investigation.get("hypotheses", [])[:3]:
                ids = ", ".join(f"#{value}" for value in item.get("evidence_event_ids", []))
                checks = "; ".join(item.get("next_checks", [])[:4])
                hypothesis_lines.append(
                    f"- **{item.get('cause', 'Unclassified')}** "
                    f"(heuristic score: {item.get('confidence', 0):.2f}) — "
                    f"{item.get('rationale', '')} Evidence: {ids}. Next checks: {checks}"
                )
            body = "\n".join([
                marker,
                "## Incident summary",
                f"- **Incident:** #{incident['id']} — {incident['title']}",
                f"- **Service:** {incident['service']}",
                f"- **Environment:** {incident['environment']}",
                f"- **Severity:** {incident['severity']}",
                f"- **Status:** {incident['status']}",
                f"- **First seen:** {incident['first_seen']}",
                f"- **Last seen:** {incident['last_seen']}",
                "",
                "## Investigation",
                investigation.get("summary", "No summary available."),
                "",
                "## Candidate hypotheses",
                "\n".join(hypothesis_lines) if hypothesis_lines else "- No evidence-linked hypothesis was returned.",
                "",
                "## Event evidence",
                "\n".join(evidence_lines) if evidence_lines else "- No event evidence available.",
                "",
                "## Important caveat",
                "This issue contains triage hypotheses, not a confirmed root cause. Verify the evidence and proposed checks before taking action.",
            ])
            response = client.post(
                f"{base_url}/issues",
                json={
                    "title": f"[CloudOps][{str(incident['severity']).upper()}] {incident['title'][:180]}",
                    "body": body,
                },
            )
            if response.is_error:
                raise GitHubIssueError("GitHub rejected the issue creation request")
            created = response.json()
    except httpx.HTTPError as exc:
        raise GitHubIssueError("GitHub API request failed") from exc

    saved = database.save_github_issue(
        int(incident["id"]), str(created["html_url"]), int(created["number"])
    )
    return {
        "issue_url": saved["github_issue_url"] if saved else created["html_url"],
        "issue_number": saved["github_issue_number"] if saved else created["number"],
        "reused": False,
    }
