import { copy } from "@/lib/copy";

interface VaultTeaserProps {
  level: number;
  tried: number;
  winners: number;
}

/** The level's sealed reward counter. It never exposes another player's attempt. */
export function VaultTeaser({ level, tried, winners }: VaultTeaserProps) {
  return (
    <aside className="vault-teaser" aria-label={copy.vaultTeaser(level, tried, winners)}>
      <svg viewBox="0 0 88 56" aria-hidden="true" className="h-12 w-[76px] shrink-0">
        <path d="M10 48h68V20L67 8H21L10 20z" fill="#FFD21F" stroke="#0B1233" strokeWidth="3" />
        <path d="M10 20h68M21 8v40M67 8v40" stroke="#0B1233" strokeWidth="3" />
        <rect x="37" y="25" width="14" height="12" rx="2" fill="#0B1233" />
        <path d="M40 25v-3a4 4 0 0 1 8 0v3" fill="none" stroke="#0B1233" strokeWidth="3" />
      </svg>
      <p className="figures text-sm leading-snug text-ink-soft">{copy.vaultTeaser(level, tried, winners)}</p>
    </aside>
  );
}
