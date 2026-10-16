"use client";

import { useId, type FormEvent, type KeyboardEvent } from "react";

import { copy } from "@/lib/copy";
import type { Goal } from "@/lib/types";

import { GoalPlate } from "./GoalPlate";

export const TASK_MAX = 300;
export const COMMAND_MAX = 1000;

interface ComposerProps {
  goals: Goal[];
  goalId: number;
  task: string;
  command: string;
  onGoal: (id: number) => void;
  onTask: (value: string) => void;
  onCommand: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  disabled: boolean;
  errors: { task?: string; command?: string };
}

function Counter({ length, max, id }: { length: number; max: number; id: string }) {
  const near = length > max * 0.9;
  return (
    <span id={id} className={`figures shrink-0 text-sm whitespace-nowrap ${near ? "font-bold text-stamp" : "text-ink-soft"}`}>
      {length} / {max}
    </span>
  );
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-2 flex gap-2 text-sm font-bold text-stamp">
      {message}
    </p>
  );
}

/** Goal plate, two fields, one button. Cmd or Ctrl plus Enter sends; nothing auto-submits. */
export function Composer(props: ComposerProps) {
  const { goals, goalId, task, command, busy, disabled, errors } = props;
  const ids = {
    task: useId(),
    taskCount: useId(),
    taskError: useId(),
    command: useId(),
    commandHint: useId(),
    commandCount: useId(),
    commandError: useId(),
    shortcut: useId(),
  };
  // While a request runs, fields go read-only and the button aria-disabled rather
  // than disabled: disabling would drop keyboard focus to the page body.
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!disabled && !busy) props.onSubmit();
  };
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  };

  const describe = (...parts: (string | false | undefined)[]) =>
    parts.filter(Boolean).join(" ") || undefined;

  return (
    <form onSubmit={submit} className="space-y-6" aria-label="Your attempt" noValidate>
      <GoalPlate goals={goals} value={goalId} onChange={props.onGoal} disabled={disabled || busy} />

      <div>
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={ids.task} className="font-bold">
            {copy.taskLabel}
          </label>
          <Counter id={ids.taskCount} length={task.length} max={TASK_MAX} />
        </div>
        <textarea
          id={ids.task}
          name="task"
          value={task}
          onChange={(e) => props.onTask(e.target.value)}
          onKeyDown={onKey}
          maxLength={TASK_MAX}
          rows={2}
          disabled={disabled}
          readOnly={busy}
          placeholder={copy.taskPlaceholder}
          aria-invalid={errors.task ? true : undefined}
          aria-describedby={describe(ids.taskCount, errors.task && ids.taskError)}
          className="field mt-2 resize-y placeholder:text-ink-soft/70"
          data-testid="task"
        />
        <FieldError id={ids.taskError} message={errors.task} />
      </div>

      <div>
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={ids.command} className="font-bold">
            {copy.commandLabel}
          </label>
          <Counter id={ids.commandCount} length={command.length} max={COMMAND_MAX} />
        </div>
        <textarea
          id={ids.command}
          name="command"
          value={command}
          onChange={(e) => props.onCommand(e.target.value)}
          onKeyDown={onKey}
          maxLength={COMMAND_MAX}
          rows={3}
          disabled={disabled}
          readOnly={busy}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          placeholder={copy.commandPlaceholder}
          aria-invalid={errors.command ? true : undefined}
          aria-describedby={describe(ids.commandHint, ids.commandCount, errors.command && ids.commandError)}
          className="field mt-2 resize-y bg-white font-mono placeholder:text-ink-soft/70"
          data-testid="command"
        />
        <p id={ids.commandHint} className="mt-2 text-sm text-ink-soft">
          {copy.neverExecuted}
        </p>
        <FieldError id={ids.commandError} message={errors.command} />
      </div>

      <div>
        <button
          type="submit"
          disabled={disabled}
          aria-disabled={busy || undefined}
          aria-describedby={ids.shortcut}
          className="btn-primary w-full aria-disabled:cursor-progress aria-disabled:bg-cobalt-deep sm:w-auto"
          data-testid="submit"
        >
          {busy ? copy.primaryBusy : copy.primary}
        </button>
        <p id={ids.shortcut} className="mt-2 text-sm text-ink-soft">
          {copy.shortcut}
        </p>
      </div>
    </form>
  );
}
