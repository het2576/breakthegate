"use client";

import type { ReactNode } from "react";

import { secondsLeft, type Phase } from "@/lib/attempt-machine";
import { copy } from "@/lib/copy";
import type { AttemptResult } from "@/lib/types";

import { CheckIcon, CrossIcon } from "./icons";

interface StatusLineProps {
  phase: Phase;
  last: AttemptResult | null;
  now: number;
  onStop: () => void;
  onRetry: () => void;
  onNewSession: () => void;
}

type Tone = "neutral" | "wait" | "good" | "bad";

const TONES: Record<Tone, string> = {
  neutral: "border-fog bg-white",
  wait: "border-ink bg-signal-wash",
  good: "border-clear bg-clear-wash",
  bad: "border-stamp bg-stamp-wash",
};

function Line({ tone, icon, children, action }: { tone: Tone; icon?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <div className={`flex min-h-[88px] items-start gap-3 rounded-field border-2 px-4 py-3 ${TONES[tone]}`}>
      {icon && <span className="mt-0.5 shrink-0">{icon}</span>}
      <div className="min-w-0 flex-1">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

function Badge({ tone, children }: { tone: "good" | "bad"; children: ReactNode }) {
  return (
    <span
      className={`inline-flex size-7 items-center justify-center rounded-full text-white ${
        tone === "good" ? "bg-clear" : "bg-stamp"
      }`}
    >
      {children}
    </span>
  );
}

function Spinner() {
  return (
    <span aria-hidden className="relative inline-flex size-7 items-center justify-center">
      <span className="absolute inset-0 rounded-full border-2 border-ink" />
      <span className="size-3 rounded-full bg-signal ring-2 ring-ink" />
    </span>
  );
}

function ResultText({ result }: { result: AttemptResult }) {
  if (result.approved) {
    return (
      <>
        <p className="sign-narrow text-lg">{copy.approved}</p>
        <p className={result.verified ? "font-bold text-ink" : "text-ink"}>
          {result.verified ? copy.verified(result.points) : copy.unverified}
        </p>
      </>
    );
  }
  const goal =
    result.verified === true ? copy.deniedGoalYes
    : result.verified === false ? copy.deniedGoalNo
    : copy.goalUnknown;
  return (
    <>
      <p className="sign-narrow text-lg">{copy.denied}</p>
      <p>{goal}</p>
    </>
  );
}

/** One reserved slot (no layout shift) that says what just happened, announced politely. */
export function StatusLine({ phase, last, now, onStop, onRetry, onNewSession }: StatusLineProps) {
  let body: ReactNode;

  switch (phase.kind) {
    case "submitting":
      body = (
        <Line tone="wait" icon={<Spinner />}>
          <p className="sign-narrow text-lg">{copy.primaryBusy}</p>
          <p className="text-ink-soft">The gate and the goal check are reading your attempt.</p>
        </Line>
      );
      break;
    case "warming": {
      const s = secondsLeft(phase.retryAt, now);
      const text =
        phase.reason === "verifier_unavailable" ? copy.verifierResting(Math.max(1, s))
        : phase.reason === "in_progress" ? "Still deciding your last attempt."
        : copy.warming;
      body = (
        <Line
          tone="wait"
          icon={<Spinner />}
          action={
            <button type="button" className="btn-quiet" onClick={onStop}>
              {copy.stopWaiting}
            </button>
          }
        >
          <p>{text}</p>
          {phase.reason === "warming_up" && <p className="figures mt-1 text-sm text-ink-soft">Trying again in {s} s.</p>}
        </Line>
      );
      break;
    }
    case "result":
      body = (
        <Line
          tone={phase.result.approved ? (phase.result.verified ? "good" : "neutral") : "bad"}
          icon={
            phase.result.approved ? (
              <Badge tone="good">
                <CheckIcon />
              </Badge>
            ) : (
              <Badge tone="bad">
                <CrossIcon />
              </Badge>
            )
          }
        >
          <ResultText result={phase.result} />
        </Line>
      );
      break;
    case "rate_limited":
      body = (
        <Line tone="wait">
          <p className="figures">{copy.rateLimit(Math.max(1, secondsLeft(phase.until, now)))}</p>
        </Line>
      );
      break;
    case "resting":
      body = (
        <Line tone="wait">
          <p className="figures">{copy.resting(Math.max(1, secondsLeft(phase.until, now)))}</p>
        </Line>
      );
      break;
    case "paused":
      body = (
        <Line
          tone="wait"
          action={
            <button type="button" className="btn-quiet" onClick={onRetry}>
              {copy.tryAgain}
            </button>
          }
        >
          <p>{copy.paused}</p>
        </Line>
      );
      break;
    case "error":
      if (phase.code === "no_session") {
        body = (
          <Line
            tone="bad"
            action={
              <button type="button" className="btn-quiet" onClick={onNewSession}>
                Start a session
              </button>
            }
          >
            <p>{copy.sessionLost}</p>
          </Line>
        );
      } else if (phase.field) {
        body = (
          <Line tone="bad">
            <p className="font-bold">Fix the highlighted field, then try again.</p>
          </Line>
        );
      } else {
        body = (
          <Line
            tone="bad"
            action={
              <button type="button" className="btn-quiet" onClick={onRetry}>
                {copy.tryAgain}
              </button>
            }
          >
            <p>{phase.code === "network" ? copy.network : phase.message}</p>
          </Line>
        );
      }
      break;
    case "idle":
      body = last ? (
        <Line tone="neutral">
          <ResultText result={last} />
        </Line>
      ) : (
        <Line tone="neutral">
          <p className="text-ink-soft">
            Pick a goal, write what the agent says it is doing, and the command. The gate answers in a
            second or two.
          </p>
        </Line>
      );
      break;
  }

  return (
    <div aria-live="polite" aria-atomic="true" data-testid="status" data-phase={phase.kind}>
      {body}
    </div>
  );
}
