"use client";

import { useRef, type KeyboardEvent } from "react";

import { copy } from "@/lib/copy";
import type { Level } from "@/lib/types";

import { ChevronIcon, LockIcon, SpeakerIcon } from "./icons";

interface HeaderProps {
  levels: Level[];
  level: number;
  onLevel: (level: number) => void;
  sound: boolean;
  onSound: (on: boolean) => void;
}

export const PANEL_ID = "level-panel";
export const tabId = (level: number) => `level-tab-${level}`;

/** Level plates as an ARIA tablist: arrow keys move, Home and End jump. */
function LevelPlates({ levels, level, onLevel }: Pick<HeaderProps, "levels" | "level" | "onLevel">) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = levels.length - 1;
    const next =
      event.key === "ArrowRight" ? (index === last ? 0 : index + 1)
      : event.key === "ArrowLeft" ? (index === 0 ? last : index - 1)
      : event.key === "Home" ? 0
      : event.key === "End" ? last
      : null;
    if (next === null) return;
    event.preventDefault();
    const target = levels[next];
    if (!target) return;
    onLevel(target.level);
    refs.current[next]?.focus();
  };

  return (
    <div role="tablist" aria-label="Levels" className="hidden items-center gap-2 sm:flex">
      {levels.map((lv, index) => {
        const active = lv.level === level;
        return (
          <button
            key={lv.level}
            ref={(el) => {
              refs.current[index] = el;
            }}
            id={tabId(lv.level)}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={PANEL_ID}
            tabIndex={active ? 0 : -1}
            aria-label={lv.locked ? `Level ${lv.level}, ${lv.name}, locked` : `Level ${lv.level}, ${lv.name}`}
            title={lv.locked ? copy.levelLocked : lv.name}
            onClick={() => onLevel(lv.level)}
            onKeyDown={(e) => onKey(e, index)}
            className={`sign inline-flex h-11 min-w-11 items-center justify-center gap-1 rounded-field border-2 px-3 text-lg leading-none ${
              active
                ? "border-ink bg-signal text-ink"
                : "border-white/55 bg-transparent text-white hover:border-white"
            }`}
          >
            {lv.locked && <LockIcon className="size-3.5" />}
            {lv.level}
          </button>
        );
      })}
    </div>
  );
}

export function Header({ levels, level, onLevel, sound, onSound }: HeaderProps) {
  return (
    <header className="bg-cobalt text-white">
      <div className="mx-auto flex w-full max-w-7xl items-center gap-4 px-4 py-3 sm:gap-6 sm:px-6 sm:py-4 lg:px-8">
        <div className="min-w-0 flex-1 sm:flex-none">
          <h1 className="sign text-lg leading-none whitespace-nowrap max-sm:[font-variation-settings:'wdth'_108] sm:text-2xl">
            {copy.title}
          </h1>
          <p className="mt-1 hidden max-w-[34ch] text-sm leading-snug text-white/90 lg:block">
            {copy.subtitle}
          </p>
        </div>

        {levels.length > 0 && <LevelPlates levels={levels} level={level} onLevel={onLevel} />}

        {levels.length > 0 && (
          <label className="relative sm:hidden">
            <span className="sr-only">Level</span>
            <select
              value={level}
              onChange={(e) => onLevel(Number(e.target.value))}
              className="sign h-11 appearance-none rounded-field border-2 border-white/70 bg-cobalt py-1 pr-9 pl-3 text-base text-white"
            >
              {levels.map((lv) => (
                <option key={lv.level} value={lv.level}>
                  Level {lv.level}
                  {lv.locked ? " (locked)" : ""}
                </option>
              ))}
            </select>
            <ChevronIcon className="pointer-events-none absolute top-1/2 right-2 size-5 -translate-y-1/2" />
          </label>
        )}

        <button
          type="button"
          aria-pressed={sound}
          onClick={() => onSound(!sound)}
          className="ml-auto inline-flex h-11 items-center gap-2 rounded-field border-2 border-white/55 px-3 text-sm font-bold hover:border-white"
        >
          <SpeakerIcon on={sound} />
          <span className="hidden whitespace-nowrap lg:inline">{sound ? copy.soundOn : copy.soundOff}</span>
          <span className="sr-only lg:hidden">{sound ? copy.soundOn : copy.soundOff}</span>
        </button>
      </div>
    </header>
  );
}
