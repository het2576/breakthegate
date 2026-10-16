"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { copy } from "@/lib/copy";

import { Turnstile, turnstileEnabled } from "./Turnstile";

interface ConsentSheetProps {
  onStart: (consent: boolean, turnstileToken?: string | null) => Promise<void>;
}

/**
 * First load: explains training use and starts the session. Consent defaults
 * to off (PRD 4.2). A bottom sheet on phones, a centered sheet on larger screens.
 * It cannot be dismissed without a choice, because there is no game without a session.
 */
export function ConsentSheet({ onStart }: ConsentSheetProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const onToken = useCallback((t: string | null) => setToken(t), []);
  const waitingForCheck = turnstileEnabled && !token;

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await onStart(consent, token);
      ref.current?.close();
    } catch {
      setError(copy.network);
      setBusy(false);
    }
  };

  return (
    <dialog
      ref={ref}
      onCancel={(e) => e.preventDefault()}
      aria-labelledby="consent-title"
      aria-describedby="consent-body"
      className="consent-sheet text-ink backdrop:bg-ink/55"
      data-testid="consent-sheet"
    >
      <div aria-hidden className="mx-auto mt-3 h-1.5 w-12 rounded-chip bg-signal ring-1 ring-ink sm:hidden" />
      <div className="px-5 pt-4 pb-6 sm:px-7 sm:pt-7">
        <h2 id="consent-title" className="sign text-2xl">
          {copy.consentTitle}
        </h2>
        <p id="consent-body" className="mt-3 max-w-[60ch] text-ink">
          {copy.consentBody}
        </p>

        <div className="mt-5 flex items-center justify-between gap-4 rounded-field border-2 border-ink bg-paper px-4 py-3">
          <span id="consent-label" className="font-bold">
            {copy.consentToggle}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={consent}
            aria-labelledby="consent-label"
            onClick={() => setConsent((c) => !c)}
            className={`relative inline-flex h-8 w-14 shrink-0 items-center rounded-chip border-2 border-ink transition-colors ${
              consent ? "bg-clear" : "bg-fog"
            }`}
            data-testid="consent-toggle"
          >
            <span
              aria-hidden
              className={`inline-block size-6 rounded-full border-2 border-ink bg-white transition-transform ${
                consent ? "translate-x-6" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
        <p className="mt-2 text-sm text-ink-soft">
          {consent ? "On. Your attempts can be used for training and tests." : "Off. Your attempts are not used for training."}
        </p>

        <Turnstile onToken={onToken} />

        {error && <p className="mt-3 font-bold text-stamp">{error}</p>}

        <button
          type="button"
          onClick={start}
          disabled={busy || waitingForCheck}
          className="btn-primary mt-6 w-full"
          data-testid="consent-start"
        >
          {copy.consentStart}
        </button>
        <p className="mt-3 text-sm text-ink-soft">{copy.neverExecuted}</p>
      </div>
    </dialog>
  );
}
