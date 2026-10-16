import Link from "next/link";

export const metadata = { title: "Privacy | Break the gate" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 lg:py-16">
      <Link href="/" className="font-bold underline underline-offset-4">Back to the game</Link>
      <h1 className="sign mt-8 text-3xl sm:text-[3rem]">Your data at the gate</h1>
      <div className="mt-8 space-y-6 text-lg leading-relaxed">
        <section className="border-t-2 border-ink pt-5">
          <h2 className="sign text-2xl">What we store</h2>
          <p className="mt-2">We store the task and command text you send, the gate and goal-check decisions, probabilities, timestamps, an anonymous session cookie, and a daily-rotating hash of your IP address. We do not ask for an account or email.</p>
        </section>
        <section className="border-t border-fog pt-5">
          <h2 className="sign text-2xl">Training use is your choice</h2>
          <p className="mt-2">Training consent starts off. You can turn it on or off in your player desk at any time. Only attempts sent while consent is on can enter training exports. Changing the switch does not rewrite past attempts.</p>
        </section>
        <section className="border-t border-fog pt-5">
          <h2 className="sign text-2xl">What other players can see</h2>
          <p className="mt-2">The leaderboard shows only an optional handle, score, level, and attempt count. It never shows tasks, commands, session IDs, or your raw attempt history.</p>
        </section>
        <section className="border-t border-fog pt-5">
          <h2 className="sign text-2xl">Delete your data</h2>
          <p className="mt-2">Use “Delete my data” in your player desk to permanently remove the current session and every attempt in it. Raw attempts are otherwise retained for 90 days. Aggregate evaluation files are retained without raw attempt text.</p>
        </section>
        <section className="border-t border-fog pt-5">
          <h2 className="sign text-2xl">A reminder</h2>
          <p className="mt-2">Commands are text only and are never run. Do not paste real secrets, private keys, access tokens, personal emails, or payment-card numbers.</p>
        </section>
      </div>
    </main>
  );
}
