"use client";

import { useState } from "react";

import { Barrier } from "@/components/Barrier";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import type { BarrierState } from "@/lib/barrier-math";

const STATES: BarrierState[] = ["idle", "thinking", "approved", "denied", "resting"];

export function BarrierLab() {
  const systemReduced = useReducedMotion();
  const [p, setP] = useState(0.31);
  const [threshold, setThreshold] = useState(0.6);
  const [state, setState] = useState<BarrierState>("idle");
  const [forceReduced, setForceReduced] = useState(false);
  const [run, setRun] = useState(0);

  const play = (next: BarrierState) => {
    setState(next);
    setRun((n) => n + 1);
  };

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8">
      <h1 className="sign text-2xl">Barrier lab</h1>
      <p className="mt-1 text-ink-soft">Development only. Drive the barrier through every state.</p>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Barrier
            p={p}
            threshold={threshold}
            state={state}
            reducedMotion={forceReduced || systemReduced}
            runKey={run}
          />
          <div className="max-w-sm">
            <p className="mb-2 text-sm text-ink-soft">Mobile sticky size</p>
            <Barrier p={p} threshold={threshold} state={state} reducedMotion={false} runKey={run} />
          </div>
        </div>

        <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
          <label className="block">
            <span className="font-bold">p(safe): {p.toFixed(2)}</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={p}
              onChange={(e) => setP(Number(e.target.value))}
              className="mt-2 block w-full accent-cobalt"
              data-testid="lab-p"
            />
          </label>
          <label className="block">
            <span className="font-bold">Threshold: {threshold.toFixed(2)}</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="mt-2 block w-full accent-cobalt"
            />
          </label>
          <fieldset>
            <legend className="font-bold">State</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {STATES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => play(s)}
                  aria-pressed={state === s}
                  className="btn-quiet aria-pressed:bg-signal"
                  data-testid={`lab-${s}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={forceReduced}
              onChange={(e) => setForceReduced(e.target.checked)}
              className="size-5 accent-cobalt"
            />
            <span>Force reduced motion</span>
          </label>
        </form>
      </div>
    </main>
  );
}
