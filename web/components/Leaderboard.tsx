import { copy } from "@/lib/copy";
import type { LeaderboardEntry } from "@/lib/types";

interface LeaderboardProps {
  entries: LeaderboardEntry[];
  level: number;
}

/** A public table with no attempt text or session identifiers. */
export function Leaderboard({ entries, level }: LeaderboardProps) {
  return (
    <section aria-labelledby="leaderboard-title" className="border-y-2 border-ink py-5" data-testid="leaderboard">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 id="leaderboard-title" className="sign text-xl">
          {copy.leaderboardTitle}
        </h2>
        <p className="figures text-sm text-ink-soft">Level {level}</p>
      </div>
      {entries.length === 0 ? (
        <p className="text-ink-soft">{copy.leaderboardEmpty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm sm:text-base">
            <thead className="border-b-2 border-ink text-sm text-ink-soft">
              <tr>
                <th scope="col" className="px-1.5 py-2 sm:px-2 font-bold">Rank</th>
                <th scope="col" className="px-1.5 py-2 sm:px-2 font-bold">Handle</th>
                <th scope="col" className="px-1.5 py-2 sm:px-2 text-right font-bold">Score</th>
                <th scope="col" className="px-1.5 py-2 sm:px-2 text-right font-bold">Attempts</th>
              </tr>
            </thead>
            <tbody className="figures">
              {entries.map((entry) => (
                <tr key={`${entry.rank}-${entry.handle}`} className="border-b border-fog last:border-0">
                  <td className="px-1.5 py-2 sm:px-2 font-bold">{entry.rank}</td>
                  <td className="max-w-[9rem] truncate px-1.5 py-2 sm:px-2">{entry.handle}</td>
                  <td className="px-1.5 py-2 sm:px-2 text-right font-bold">{entry.score}</td>
                  <td className="px-1.5 py-2 sm:px-2 text-right">{entry.attempts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
