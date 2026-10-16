"use client";

import { copy } from "@/lib/copy";
import type { AttemptResult, LayerResult, LevelsResponse, PublicLayer } from "@/lib/types";

import { CheckIcon, CrossIcon, SkipIcon } from "./icons";

interface ChecksProps {
  layers: PublicLayer[];
  result: AttemptResult | null;
  goalCheck: LevelsResponse["goal_check"];
}

type RowStatus = "pass" | "fail" | "skip" | "pending";

function StatusMark({ status }: { status: RowStatus }) {
  const base = "inline-flex size-7 shrink-0 items-center justify-center rounded-full";
  if (status === "pass")
    return (
      <span className={`${base} bg-clear text-white`}>
        <CheckIcon />
        <span className="sr-only">Passed</span>
      </span>
    );
  if (status === "fail")
    return (
      <span className={`${base} bg-stamp text-white`}>
        <CrossIcon />
        <span className="sr-only">Said no</span>
      </span>
    );
  if (status === "skip")
    return (
      <span className={`${base} border-2 border-fog text-ink-soft`}>
        <SkipIcon />
        <span className="sr-only">Skipped</span>
      </span>
    );
  return <span className={`${base} border-2 border-dashed border-ink-soft/60`} aria-hidden />;
}

function Row({
  label,
  question,
  status,
  detail,
  deciding,
}: {
  label: string;
  question: string | null;
  status: RowStatus;
  detail: string;
  deciding: boolean;
}) {
  return (
    <li className="flex gap-3 py-3">
      <StatusMark status={status} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-bold">{label}</span>
          {deciding && (
            <span className="rounded-chip bg-ink px-2 py-0.5 text-sm font-bold text-white">Decided it</span>
          )}
        </div>
        <p className={status === "fail" ? "font-bold text-stamp" : status === "pass" ? "text-ink" : "text-ink-soft"}>
          {detail}
        </p>
        {question && <p className="mt-1 text-sm text-ink-soft">Asked: {question}</p>}
      </div>
    </li>
  );
}

/** The level's checks in the order they run, with what each one said (PRD 11.5 LayerList). */
export function Checks({ layers, result, goalCheck }: ChecksProps) {
  const byName = new Map<string, LayerResult>((result?.layers ?? []).map((l) => [l.name, l]));
  const floorDenied = result?.layers.some((l) => l.name === "rule_floor" && !l.passed) ?? false;

  const goalStatus: RowStatus =
    !result ? "pending" : result.verified === true ? "pass" : result.verified === false ? "fail" : "skip";
  const goalDetail =
    !result ? `Needs ${goalCheck.threshold.toFixed(2)}. Reads only your command and the goal.`
    : result.verified === true ? "Your command does the goal."
    : result.verified === false ? "Your command does not do the goal."
    : "Could not run this time.";

  return (
    <section aria-labelledby="checks-title">
      <h2 id="checks-title" className="sign-narrow text-xl">
        {copy.checksTitle}
      </h2>
      {!result && <p className="mt-1 text-sm text-ink-soft">{copy.checksIdle}</p>}
      <ol className="mt-2 divide-y divide-fog border-y border-fog" data-testid="checks">
        {layers.map((layer) => {
          const r = byName.get(layer.name);
          const status: RowStatus = r ? (r.passed ? "pass" : "fail") : result ? "skip" : "pending";
          const detail = r
            ? r.detail
            : result && floorDenied
              ? "Skipped. The pattern filter already said no."
              : (layer.description ?? "Not run yet.");
          return (
            <Row
              key={layer.name}
              label={layer.label}
              question={layer.question}
              status={status}
              detail={detail}
              deciding={!!result && result.deciding_layer === layer.name}
            />
          );
        })}
      </ol>
      <ul className="border-b border-dashed border-ink-soft/40" aria-label="Goal check">
        <Row label="Goal check" question={goalCheck.question} status={goalStatus} detail={goalDetail} deciding={false} />
      </ul>
    </section>
  );
}
