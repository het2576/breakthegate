import Link from "next/link";

import type { GateReport, Interval, ReportModel } from "@/lib/types";

const pct = (value: number) => `${Math.round(value * 100)}%`;
const range = (value: Interval) => `${pct(value.v)} (${pct(value.lo)} to ${pct(value.hi)})`;

interface MetricRow {
  model: ReportModel;
  family: string;
  asr?: Interval;
  fbr?: Interval;
}

function rows(report: GateReport): MetricRow[] {
  return report.models.flatMap((model) => {
    const families = new Set([...Object.keys(model.asr), ...Object.keys(model.fbr)]);
    return [...families].sort().map((family) => ({ model, family, asr: model.asr[family], fbr: model.fbr[family] }));
  });
}

function RangePlot({ rows: values }: { rows: MetricRow[] }) {
  const plotted = values.filter((row) => row.asr);
  if (!plotted.length) return null;
  const height = 42 + plotted.length * 42;
  return (
    <figure className="report-plot" aria-labelledby="range-plot-title">
      <figcaption id="range-plot-title" className="sign text-xl">Attack success on held-out data</figcaption>
      <svg viewBox={`0 0 640 ${height}`} role="img" aria-labelledby="range-plot-title range-plot-desc" className="mt-4 w-full" preserveAspectRatio="xMinYMin meet">
        <desc id="range-plot-desc">Each horizontal line shows a model and attack family’s 95 percent interval. The dot is the measured attack success rate.</desc>
        <line x1="184" y1="22" x2="604" y2="22" stroke="currentColor" strokeWidth="2" />
        {[0, 25, 50, 75, 100].map((tick) => {
          const x = 184 + tick * 4.2;
          return <g key={tick}><line x1={x} y1="18" x2={x} y2={height - 6} stroke="currentColor" strokeOpacity="0.14" /><text x={x} y="14" textAnchor="middle" className="fill-ink-soft text-[11px]">{tick}%</text></g>;
        })}
        {plotted.map((row, index) => {
          const value = row.asr!;
          const y = 48 + index * 42;
          const scale = (n: number) => 184 + Math.max(0, Math.min(1, n)) * 420;
          return <g key={`${row.model.name}-${row.family}`}>
            <text x="0" y={y + 4} className="fill-ink text-[13px]">{row.model.name} / {row.family}</text>
            <line x1={scale(value.lo)} y1={y} x2={scale(value.hi)} y2={y} stroke="#1f3fd6" strokeWidth="5" strokeLinecap="round" />
            <circle cx={scale(value.v)} cy={y} r="6" fill="#ffd21f" stroke="#0b1233" strokeWidth="2" />
          </g>;
        })}
      </svg>
    </figure>
  );
}

export function ReportBoard({ report }: { report: GateReport | null }) {
  if (!report) {
    return (
      <main className="report-shell">
        <Link href="/" className="font-bold underline underline-offset-4">Back to the game</Link>
        <section className="report-empty" data-testid="report-empty">
          <p className="sign text-2xl">The inspection board is empty.</p>
          <p className="mt-3 max-w-prose text-lg">The first evaluation has not been published yet. Numbers appear here only after a saved evaluation is available.</p>
        </section>
      </main>
    );
  }
  const tableRows = rows(report);
  return (
    <main className="report-shell" data-testid="report">
      <header className="report-masthead">
        <Link href="/" className="font-bold underline underline-offset-4">Back to the game</Link>
        <p className="mt-10 text-sm font-bold">A public record of what the gate did</p>
        <h1 className="sign mt-2 text-3xl sm:text-[3rem]">Gate report</h1>
        <dl className="report-meta figures">
          <div><dt>Gate version</dt><dd>{report.gate_version}</dd></div>
          {report.date && <div><dt>Published</dt><dd>{report.date}</dd></div>}
        </dl>
      </header>

      {tableRows.length ? (
        <>
          <RangePlot rows={tableRows} />
          <section className="mt-12 overflow-x-auto" aria-labelledby="metrics-title">
            <h2 id="metrics-title" className="sign text-2xl">Held-out measurements</h2>
            <table className="report-table mt-4 min-w-[44rem]">
              <caption>Attack success and false-block rates. Intervals are 95 percent bootstrap intervals.</caption>
              <thead><tr><th>Model</th><th>Family</th><th>Attack success</th><th>False block</th><th>Rows</th></tr></thead>
              <tbody>{tableRows.map((row) => <tr key={`${row.model.name}-${row.family}`}><th scope="row">{row.model.name}</th><td>{row.family}</td><td>{row.asr ? range(row.asr) : "Not measured"}</td><td>{row.fbr ? range(row.fbr) : "Not measured"}</td><td className="figures">{row.model.n.dangerous} dangerous, {row.model.n.safe} safe</td></tr>)}</tbody>
            </table>
          </section>
        </>
      ) : <p className="mt-12 text-lg">This evaluation has no family measurements to display.</p>}

      <section className="report-limits" aria-labelledby="limits-title">
        <h2 id="limits-title" className="sign text-2xl">Known limits</h2>
        <ul>{report.limits.map((limit) => <li key={limit}>{limit}</li>)}</ul>
      </section>
    </main>
  );
}
