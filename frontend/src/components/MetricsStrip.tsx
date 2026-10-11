import type { Metrics, Proposal, Strategy } from "@/api/types";

interface Props {
  committed: Metrics;
  proposal: Proposal | null;
  strategy: Strategy | null;
}

function Cell({ label, now, next, unit = "", better }: { label: string; now: number | string; next?: number | string; unit?: string; better?: "lower" }) {
  const changed = next !== undefined && next !== now;
  const worse = changed && better === "lower" && typeof now === "number" && typeof next === "number" && next > now;
  return (
    <div className="min-w-[92px] px-2.5 py-1.5">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="tabular text-[15px] font-semibold">
        {now}{unit}
        {changed && (
          <span className={`ml-1.5 text-[12px] ${worse ? "text-proposed" : "text-ok"}`} aria-label={`proposed ${next}${unit}`}>
            → {next}{unit}
          </span>
        )}
      </div>
    </div>
  );
}

/** Committed metrics with the ready proposal's values beside them. Scope: future work from the current time. */
export function MetricsStrip({ committed, proposal, strategy }: Props) {
  const p = proposal?.status === "ready" ? proposal.proposed_snapshot?.metrics : undefined;
  const d = proposal?.status === "ready" ? proposal.comparison.find((c) => c.strategy === strategy)?.diff_metrics : undefined;
  const em = p?.emergencies.at(-1) ?? committed.emergencies.at(-1);
  return (
    <div className="flex flex-wrap items-stretch divide-x divide-line rounded-[12px] border border-line bg-panel" data-testid="metrics-strip" aria-label="Schedule metrics, future work from now" title="Scope: work after the current simulated time">
      <Cell label="Future travel" now={committed.travel_min} next={p?.travel_min} unit=" min" better="lower" />
      <Cell label="Unassigned jobs" now={committed.unassigned_jobs} next={p?.unassigned_jobs} better="lower" />
      <Cell label="Soft SLA misses" now={committed.soft_sla_violations} next={p?.soft_sla_violations} better="lower" />
      <Cell label="Hard violations" now={committed.hard_constraint_violations} next={p?.hard_constraint_violations} better="lower" />
      {d && <Cell label="Existing jobs changed" now={d.changed_existing_jobs} />}
      {d && <Cell label="Total start shift" now={d.absolute_start_shift_min} unit=" min" />}
      <Cell label="Emergency response" now={em && em.response_min !== null ? `${em.response_min} min${em.deadline_met ? "" : " (late)"}` : "—"} />
      <div className="flex items-center px-2.5 text-[11px] text-muted">Scope: work after now</div>
      
    </div>
  );
}
