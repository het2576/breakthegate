import type { Metadata } from "next";

import { ReportBoard } from "@/components/ReportBoard";
import { getGateReport } from "@/lib/report";

export const metadata: Metadata = { title: "Gate report | Break the gate" };
// Always reads the latest eval from the API; a prerendered shell would show stale
// numbers, which PRD 11.5 forbids ("every UI number comes from the API or an eval file").
export const instant = false;

export default async function ReportPage() {
  return <ReportBoard report={await getGateReport()} />;
}
