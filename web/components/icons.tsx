// Small inline icons. Always paired with a word: status never relies on color alone.

interface IconProps {
  className?: string;
}

export function CheckIcon({ className = "size-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden>
      <path d="M3 8.5l3.2 3.2L13 5" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CrossIcon({ className = "size-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden>
      <path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" />
    </svg>
  );
}

export function SkipIcon({ className = "size-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden>
      <path d="M3.5 8h9" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" />
    </svg>
  );
}

export function LockIcon({ className = "size-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden>
      <rect x={3} y={7} width={10} height={7} rx={1.5} fill="currentColor" />
      <path d="M5.5 7V5a2.5 2.5 0 015 0v2" fill="none" stroke="currentColor" strokeWidth={1.8} />
    </svg>
  );
}

export function ChevronIcon({ className = "size-5" }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden>
      <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SpeakerIcon({ on, className = "size-5" }: IconProps & { on: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden>
      <path d="M3 8h3l4-3.5v11L6 12H3z" fill="currentColor" />
      {on ? (
        <path d="M13 7.5a3.5 3.5 0 010 5M15 5.5a6.5 6.5 0 010 9" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
      ) : (
        <path d="M13 8l4 4M17 8l-4 4" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
      )}
    </svg>
  );
}
