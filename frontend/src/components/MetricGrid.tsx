interface Metric {
  label: string;
  value: number;
}

export function MetricGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {metrics.map((m) => (
        <div
          key={m.label}
          className="border border-ink-900/10 bg-white/70 p-4 transition hover:border-brand-500/30"
        >
          <p className="text-xs uppercase tracking-wide text-ink-700">{m.label}</p>
          <p className="mt-1 font-display text-2xl font-semibold tabular-nums">{m.value}</p>
        </div>
      ))}
    </div>
  );
}
