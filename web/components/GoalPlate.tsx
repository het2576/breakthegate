"use client";

import { copy } from "@/lib/copy";
import type { Goal } from "@/lib/types";

import { ChevronIcon } from "./icons";

interface GoalPlateProps {
  goals: Goal[];
  value: number;
  onChange: (goalId: number) => void;
  disabled: boolean;
}

/**
 * The goal as a destination sign: the full goal text, never truncated, with the
 * native select laid over it. Tapping the plate opens the platform picker, and
 * keyboard and screen readers get a real select (PRD 11.5 GoalSelect).
 */
export function GoalPlate({ goals, value, onChange, disabled }: GoalPlateProps) {
  const current = goals.find((g) => g.id === value);
  return (
    <div>
      <label htmlFor="goal" className="block font-bold">
        {copy.goalLabel}
      </label>
      <div
        className={`goal-plate relative mt-2 flex items-start gap-3 rounded-field border-2 px-4 py-3 ${
          disabled ? "border-fog bg-paper" : "border-ink bg-signal-wash"
        }`}
      >
        <span aria-hidden className="sign-narrow figures mt-0.5 shrink-0 text-lg text-ink-soft">
          {String(value).padStart(2, "0")}
        </span>
        <span aria-hidden className="sign-narrow min-w-0 flex-1 text-lg leading-snug" data-testid="goal-text">
          {current?.text ?? ""}
        </span>
        <span aria-hidden className="mt-0.5 inline-flex shrink-0 items-center gap-1 text-sm font-bold text-ink-soft">
          <span className="hidden lg:inline">{copy.goalChange}</span>
          <ChevronIcon />
        </span>
        <select
          id="goal"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0 disabled:cursor-not-allowed"
        >
          {goals.map((g) => (
            <option key={g.id} value={g.id}>
              {g.id}. {g.text}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
