import { mkdir } from "node:fs/promises";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const frontend = path.join(root, "frontend");
const require = createRequire(path.join(frontend, "package.json"));
const { chromium } = require("playwright");
const artifactDir = path.join(root, "artifacts");
const dbPath = path.join(artifactDir, "snapshot.db");
const token = "ci-only-cloudops-snapshot-token";
const children = [];

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: options.cwd ?? root,
    env: {
      ...process.env,
      CLOUDOPS_DB_PATH: dbPath,
      CLOUDOPS_ALERTMANAGER_WEBHOOK_TOKEN: token,
      CLOUDOPS_CORS_ORIGINS: "http://127.0.0.1:3000",
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000",
      ...options.env,
    },
    stdio: "inherit",
  });
  children.push(child);
  return child;
}

async function waitFor(url, label) {
  let lastError;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = new Error(`${label} returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await delay(1000);
  }
  throw new Error(`Timed out waiting for ${label}: ${lastError}`);
}

try {
  await mkdir(artifactDir, { recursive: true });
  start("python", ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"]);
  await waitFor("http://127.0.0.1:8000/health", "API health");
  start("npm", ["run", "dev", "--", "--hostname", "127.0.0.1"], {
    cwd: frontend,
    env: { NEXT_TELEMETRY_DISABLED: "1" },
  });
  await waitFor("http://127.0.0.1:3000", "dashboard");

  // Exercise the authenticated external-ingestion path, not a pre-seeded database.
  const ingest = await fetch("http://127.0.0.1:8000/api/v1/integrations/alertmanager", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      receiver: "cloudops-ci-snapshot",
      status: "firing",
      alerts: [{
        status: "firing",
        labels: {
          alertname: "SnapshotIntegrationCheck",
          service: "checkout-api",
          environment: "ci",
          severity: "critical",
        },
        annotations: {
          summary: "Runtime snapshot: Alertmanager webhook reached CloudOps AI",
          description: "CI verifies authenticated alert ingestion and dashboard rendering.",
        },
        startsAt: new Date().toISOString(),
        generatorURL: "https://prometheus.example.invalid/graph",
        fingerprint: "ci-snapshot-integration-check",
      }],
    }),
  });
  if (!ingest.ok) throw new Error(`Alertmanager ingestion failed: ${ingest.status} ${await ingest.text()}`);

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1 });
    await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle", timeout: 60000 });
    await page.getByText("Incident queue").waitFor({ timeout: 30000 });
    await page.getByText("Runtime snapshot: Alertmanager webhook reached CloudOps AI").waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(artifactDir, "cloudops-dashboard.png"), fullPage: true });
    console.log("Captured runtime dashboard screenshot at artifacts/cloudops-dashboard.png");
  } finally {
    await browser.close();
  }
} finally {
  for (const child of children) child.kill("SIGTERM");
}
