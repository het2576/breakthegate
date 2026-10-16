"use client";

import { useState } from "react";

import { hintsFor } from "@/lib/hints";

interface HintPanelProps {
  level: number;
  goalId: number;
  deniedInARow: number;
}

/** Opt-in hints, one at a time. Remount with a new key when level or goal changes. */
export function HintPanel({ level, goalId, deniedInARow }: HintPanelProps) {
  const hints = hintsFor(level, goalId);
  const [shown, setShown] = useState(0);
  if (hints.length === 0) return null;

  const stuck = deniedInARow >= 3 && shown === 0;
  return (
    <section aria-labelledby="hint-title" className="mt-8 rounded-field border-2 border-ink bg-white p-5" data-testid="hints">
      <h3 id="hint-title" className="sign text-lg">
        Stuck?
      </h3>
      <p className="mt-1 text-ink-soft">
        {stuck ? "Three misses in a row. A hint might help." : "Hints show one at a time, so you only see what you ask for."}
      </p>

      {shown > 0 && (
        <ol className="mt-3 space-y-2" aria-live="polite" data-testid="hint-list">
          {hints.slice(0, shown).map((hint, i) => (
            <li key={hint} className="flex gap-3">
              <span
                aria-hidden
                className="sign figures mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-signal text-sm"
              >
                {i + 1}
              </span>
              <span>{hint}</span>
            </li>
          ))}
        </ol>
      )}

      {shown < hints.length ? (
        <button
          type="button"
          className="btn-quiet mt-4"
          onClick={() => setShown((n) => n + 1)}
          data-testid="hint-next"
        >
          {shown === 0 ? "Show a hint" : "Show another hint"}
        </button>
      ) : (
        <p className="mt-3 text-sm text-ink-soft">That is every hint for this goal. Keep tweaking one thing at a time.</p>
      )}
    </section>
  );
}
