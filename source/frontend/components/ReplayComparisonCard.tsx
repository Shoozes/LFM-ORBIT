import type { ReplayComparison } from "../types/replay";

type ReplayComparisonCardProps = {
  comparison: ReplayComparison;
};

export default function ReplayComparisonCard({ comparison }: ReplayComparisonCardProps) {
  return (
    <div data-testid="replay-comparison" className="rounded border border-violet-200 bg-violet-50 px-3 py-3 text-xs text-violet-950">
      <p className="font-semibold uppercase tracking-wider text-[10px] text-violet-700">Additive rescan comparison</p>
      <p className="mt-1 leading-relaxed">
        Original cached proof stays unchanged. {comparison.changed_count} changed / {comparison.unchanged_count} unchanged across {comparison.current_alert_count} current alerts.
      </p>
      <p className="mt-1 text-[10px] uppercase tracking-wider text-violet-700">
        {comparison.source_replay_id} · {comparison.prior_scoring_basis} → {comparison.current_scoring_basis}
      </p>
      {comparison.rows.filter((row) => row.status === "changed").map((row) => (
        <p key={row.cell_id} className="mt-2 border-t border-violet-200 pt-2">
          <strong>{row.cell_id}</strong>: {row.changes.join(", ") || "model review"} ({row.prior.priority} → {row.current.priority})
        </p>
      ))}
    </div>
  );
}
