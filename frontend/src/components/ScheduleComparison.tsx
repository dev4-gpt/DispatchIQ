import { useState } from "react";
import {
  ArrowRight,
  ArrowRightLeft,
  Clock,
  Plus,
  CircleSlash,
} from "lucide-react";
import type { Change, Placement, Proposal } from "@/api/types";
import { Button } from "@/components/ui/button";
import { index, type Indexed } from "@/lib/schedule";
import { hhmm } from "@/state/dispatch";

const kinds = {
  added: { icon: Plus, text: "Added" },
  reassigned: { icon: ArrowRightLeft, text: "Reassigned" },
  shifted: { icon: Clock, text: "Time shifted" },
  unassigned: { icon: CircleSlash, text: "Unassigned" },
};

function PlacementCell({
  placement,
  view,
}: {
  placement: Placement | undefined | null;
  view: Indexed;
}) {
  return placement ? (
    <span className="placement-cell">
      <strong>
        {view.techs.get(placement.technician_id)?.name ??
          placement.technician_id}
      </strong>
      <span className="tabular">
        {hhmm(placement.start_min)}–{hhmm(placement.end_min)}
      </span>
    </span>
  ) : (
    <span className="placement-cell unassigned-placement">Not assigned</span>
  );
}

/** Compare explicit server intervals. Change labels come from the proposal, never inferred benefits. */
export function ScheduleComparison({
  proposal,
  committed,
  onSelectJob,
}: {
  proposal: Proposal;
  committed: Indexed;
  onSelectJob: (id: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const next = proposal.proposed_snapshot
    ? index(proposal.proposed_snapshot)
    : null;
  if (!next) return null;
  const changes = new Map(proposal.changes.map((c) => [c.job_id, c]));
  const changedIds = proposal.changes.map((c) => c.job_id);
  const ids = showAll
    ? [
        ...changedIds,
        ...[...new Set([...committed.jobs.keys(), ...next.jobs.keys()])].filter(
          (id) => !changes.has(id),
        ),
      ]
    : changedIds;
  return (
    <section
      className="schedule-comparison"
      aria-label="Appointment comparison"
      data-testid="schedule-comparison"
    >
      <header>
        <h3>
          What changes <span>{proposal.changes.length}</span>
        </h3>
        <Button
          size="sm"
          variant="ghost"
          aria-pressed={showAll}
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? "Show changed jobs" : "Show all jobs"}
        </Button>
      </header>
      <div
        className="comparison-rows"
        tabIndex={0}
        aria-label="Scrollable current and proposed appointments"
      >
        <table>
          <caption className="sr-only">
            {showAll ? "All appointments" : "Changed appointments"}, approved
            versus proposed schedule
          </caption>
          <thead>
            <tr>
              <th scope="col">Job</th>
              <th scope="col">Current</th>
              <th scope="col">Proposed</th>
            </tr>
          </thead>
          <tbody>
            {ids.map((id) => {
              const change: Change | undefined = changes.get(id);
              const job = next.jobs.get(id) ?? committed.jobs.get(id);
              const kind = change ? kinds[change.kind] : null;
              const Icon = kind?.icon;
              const before = committed.byJob.get(id);
              const after = next.byJob.get(id);
              const shift =
                before && after ? after.start_min - before.start_min : 0;
              return (
                <tr
                  key={id}
                  data-testid={change ? `change-${id}` : `unchanged-${id}`}
                  data-comparison-change={change?.kind ?? "unchanged"}
                >
                  <th scope="row">
                    <button
                      onClick={() => onSelectJob(id)}
                      title={job?.customer.name}
                    >
                      <span>
                        {Icon && <Icon size={12} aria-hidden />}
                        <strong>{id}</strong>
                      </span>
                      <small>
                        {kind?.text ?? "Unchanged"}
                        {shift !== 0 && (
                          <span className="tabular">
                            {" "}
                            · {shift > 0 ? "+" : ""}
                            {shift}m
                          </span>
                        )}
                      </small>
                    </button>
                  </th>
                  <td>
                    <PlacementCell placement={before} view={committed} />
                  </td>
                  <td>
                    <PlacementCell placement={after} view={next} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!ids.length && (
          <p className="comparison-empty">No assignment changes.</p>
        )}
      </div>
      <p className="comparison-count">
        {ids.length} of{" "}
        {new Set([...committed.jobs.keys(), ...next.jobs.keys()]).size} jobs ·{" "}
        <ArrowRight size={11} aria-hidden /> Approval applies the proposed
        column.
      </p>
      <details className="review-disclosure">
        <summary>Reasons for appointment changes</summary>
        <ul className="change-reasons">
          {proposal.changes.map((c) => (
            <li key={c.job_id}>
              <strong>{c.job_id}</strong> {c.explanation}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
