import { notFound } from "next/navigation";

import { BarrierLab } from "./BarrierLab";

export const metadata = { title: "Barrier lab" };

// A Storybook-style demo of the barrier (PRD P5). Hidden in production builds
// unless ENABLE_DEV_PAGES=1 (used by the e2e run).
export default function BarrierLabPage() {
  if (process.env.NODE_ENV === "production" && process.env.ENABLE_DEV_PAGES !== "1") {
    notFound();
  }
  return <BarrierLab />;
}
