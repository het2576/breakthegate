"use client";

import { useEffect, useRef } from "react";

import { copy } from "@/lib/copy";

export function HowSteps({ compact = false }: { compact?: boolean }) {
  return (
    <ol className={`mt-3 space-y-2 ${compact ? "text-[0.95rem] leading-snug sm:text-base" : ""}`}>
      {copy.howSteps.map((step, i) => (
        <li key={step} className="flex gap-3">
          <span
            aria-hidden
            className="sign figures mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-signal text-sm"
          >
            {i + 1}
          </span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
}

/** Full explanation, opened from the header at any time. */
export function HowToPlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      dialog.querySelector<HTMLElement>("#how-title")?.focus({ preventScroll: true });
      dialog.scrollTop = 0;
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="how-title"
      className="consent-sheet text-ink backdrop:bg-ink/55"
      data-testid="how-to-play"
    >
      <div className="px-5 pt-5 pb-6 sm:px-7 sm:pt-7">
        <h2 id="how-title" tabIndex={-1} className="sign text-2xl focus-visible:shadow-none focus-visible:outline-none">
          {copy.guideTitle}
        </h2>
        <p className="mt-3 max-w-[60ch]">{copy.howIntro}</p>
        <HowSteps />
        <p className="mt-4 rounded-field border-2 border-ink bg-paper px-4 py-3 font-bold">{copy.howTip}</p>
        <p className="mt-3 text-ink-soft">{copy.howLevels}</p>
        <p className="mt-3 text-sm text-ink-soft">{copy.neverExecuted}</p>
        <button type="button" className="btn-primary mt-6 w-full" onClick={onClose} data-testid="how-close">
          Got it
        </button>
      </div>
    </dialog>
  );
}
