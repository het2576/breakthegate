"use client";

import { useEffect, useRef, useState } from "react";

import { fmt } from "@/lib/barrier-math";
import { copy } from "@/lib/copy";
import type { Goal, HistoryItem } from "@/lib/types";

import { CheckIcon, CrossIcon } from "./icons";

interface TimelineProps {
  history: HistoryItem[]; // newest first, as the API returns it
  threshold: number;
  goals: Goal[];
}

function verdict(item: HistoryItem): string {
  if (!item.approved) return "Denied";
  return item.verified ? "Approved, does the goal" : "Approved, not the goal";
}

function tickClass(item: HistoryItem): string {
  if (!item.approved) return "bg-stamp border-stamp";
  return item.verified ? "bg-clear border-clear" : "bg-white border-clear";
}

function Detail({ item, goals, onClose }: { item: HistoryItem; goals: Goal[]; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);
  const goal = goals.find((g) => g.id === item.goal_id)?.text ?? `Goal ${item.goal_id}`;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="attempt-detail-title"
      className="m-auto w-[min(100vw-2rem,40rem)] rounded-housing border-2 border-ink bg-white p-0 text-ink backdrop:bg-ink/55"
      data-testid="attempt-detail"
    >
      <div className="flex items-start justify-between gap-4 border-b-2 border-ink px-5 py-4">
        <div>
          <h2 id="attempt-detail-title" className="sign-narrow text-xl">
            Attempt on level {item.level}
          </h2>
          <p className="text-sm text-ink-soft">{new Date(item.created_at).toLocaleString()}</p>
        </div>
        <button type="button" className="btn-quiet" onClick={() => ref.current?.close()}>
          Close
        </button>
      </div>
      <div className="space-y-4 px-5 py-4">
        <p className="flex flex-wrap items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-chip px-3 py-1 font-bold text-white ${
              item.approved ? "bg-clear" : "bg-stamp"
            }`}
          >
            {item.approved ? <CheckIcon /> : <CrossIcon />}
            {verdict(item)}
          </span>
          <span className="sign figures text-2xl">{fmt(item.p_safe)}</span>
          <span className="figures text-ink-soft">needs {fmt(item.threshold)}</span>
          {item.points > 0 && <span className="figures font-bold text-clear">+{item.points}</span>}
        </p>
        <div>
          <p className="text-sm font-bold">{copy.goalLabel}</p>
          <p>{goal}</p>
        </div>
        <div>
          <p className="text-sm font-bold">{copy.taskLabel}</p>
          <p className="break-words whitespace-pre-wrap">{item.task}</p>
        </div>
        <div>
          <p className="text-sm font-bold">Command</p>
          <pre className="mt-1 max-h-48 overflow-auto rounded-field border-2 border-ink bg-paper px-3 py-2 font-mono text-sm break-all whitespace-pre-wrap">
            {item.command}
          </pre>
        </div>
        <ul className="divide-y divide-fog border-y border-fog">
          {item.layers.map((layer) => (
            <li key={layer.name} className="flex items-start gap-2 py-2 text-sm">
              <span className={layer.passed ? "text-clear" : "text-stamp"}>
                {layer.passed ? <CheckIcon /> : <CrossIcon />}
              </span>
              <span>
                <span className="font-bold">{layer.name.replace("_", " ")}</span>: {layer.detail}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </dialog>
  );
}

/** One tick per attempt: height is p(safe), color is the verdict, dashed line is the threshold. */
export function AttemptTimeline({ history, threshold, goals }: TimelineProps) {
  const [open, setOpen] = useState<HistoryItem | null>(null);
  const strip = useRef<HTMLDivElement>(null);
  const items = [...history].reverse();
  const points = history.reduce((sum, h) => sum + h.points, 0);

  useEffect(() => {
    strip.current?.scrollTo({ left: strip.current.scrollWidth });
  }, [history.length]);

  return (
    <section aria-labelledby="attempts-title">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="attempts-title" className="sign-narrow text-xl">
          {copy.attemptsTitle}
        </h2>
        <p className="figures text-sm text-ink-soft" data-testid="attempt-summary">
          {history.length} {history.length === 1 ? "attempt" : "attempts"}, {points} points on this level
        </p>
      </div>

      {items.length === 0 ? (
        <p className="mt-3 rounded-field border-2 border-dashed border-fog px-4 py-6 text-center text-ink-soft">
          {copy.emptyHistory}
        </p>
      ) : (
        <>
          <div ref={strip} className="mt-3 overflow-x-auto pb-2">
            <div className="relative h-28" style={{ width: `max(100%, ${items.length * 44 + 8}px)` }}>
              <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 z-10 border-t-2 border-dashed border-ink/70"
                style={{ bottom: `calc(${threshold} * (100% - 8px) * 0.92 + 8px)` }}
              />
              <ol className="flex h-full items-end border-b-2 border-ink px-1" data-testid="timeline">
                {items.map((item, i) => (
                  <li key={item.attempt_id} className="flex h-full items-end">
                    <button
                      type="button"
                      onClick={() => setOpen(item)}
                      aria-label={`Attempt ${i + 1}: ${verdict(item)}, probability safe ${fmt(item.p_safe)}`}
                      className="group flex h-full w-11 items-end justify-center"
                    >
                      <span
                        className={`block w-[18px] rounded-t-[3px] border-2 ${tickClass(item)} group-hover:brightness-110`}
                        style={{ height: `calc(${Math.max(item.p_safe, 0.02)} * (100% - 8px) * 0.92 + 8px)` }}
                      />
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft" aria-label="Legend">
            <li className="flex items-center gap-1.5">
              <span className="inline-block size-3 rounded-sm bg-clear" aria-hidden /> Approved, does the goal
            </li>
            <li className="flex items-center gap-1.5">
              <span className="inline-block size-3 rounded-sm border-2 border-clear bg-white" aria-hidden /> Approved, not the goal
            </li>
            <li className="flex items-center gap-1.5">
              <span className="inline-block size-3 rounded-sm bg-stamp" aria-hidden /> Denied
            </li>
            <li className="flex items-center gap-1.5">
              <span className="inline-block w-4 border-t-2 border-dashed border-ink" aria-hidden /> needs {fmt(threshold)}
            </li>
          </ul>
        </>
      )}

      {open && <Detail item={open} goals={goals} onClose={() => setOpen(null)} />}
    </section>
  );
}
