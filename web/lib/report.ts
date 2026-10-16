import "server-only";

import type { GateReport } from "./types";

function isReport(value: unknown): value is GateReport {
  if (!value || typeof value !== "object") return false;
  const report = value as Partial<GateReport>;
  return typeof report.gate_version === "string" && Array.isArray(report.models) && Array.isArray(report.limits);
}

export async function getGateReport(): Promise<GateReport | null> {
  const origin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
  const secret = process.env.PROXY_SECRET ?? "dev-proxy-secret";
  try {
    const response = await fetch(`${origin}/api/report`, {
      cache: "no-store",
      headers: { "x-btg-proxy-secret": secret },
    });
    if (!response.ok) return null;
    const body: unknown = await response.json();
    if (!body || typeof body !== "object") return null;
    const report = (body as { report?: unknown }).report;
    return isReport(report) ? report : null;
  } catch {
    return null;
  }
}
