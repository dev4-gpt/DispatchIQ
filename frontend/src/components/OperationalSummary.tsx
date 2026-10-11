import {
  AlertTriangle,
  ClipboardList,
  ShieldCheck,
  Siren,
  Users,
} from "lucide-react";
import type { Snapshot } from "@/api/types";
import { Tooltip } from "@/components/ui/tooltip";

/** Facts about the committed snapshot, with no inferred probability or fabricated forecast. */
export function OperationalSummary({
  snapshot,
  pending,
}: {
  snapshot: Snapshot;
  pending: boolean;
}) {
  const available = snapshot.technicians.filter(
    (t) =>
      t.availability === "available" &&
      t.shift_start_min <= snapshot.now_min &&
      t.shift_end_min > snapshot.now_min,
  ).length;
  const jobById = new Map(snapshot.jobs.map((j) => [j.id, j]));
  const atRisk = new Set(snapshot.schedule.unassigned_job_ids);
  for (const a of snapshot.schedule.assignments) {
    const j = jobById.get(a.job_id);
    if (!j || a.start_min <= snapshot.now_min) continue;
    if (
      (j.soft_promised_start_min !== null &&
        a.start_min > j.soft_promised_start_min) ||
      (j.deadline_start_min !== null && a.start_min > j.deadline_start_min)
    )
      atRisk.add(j.id);
  }
  for (const violation of snapshot.validation.violations)
    if (violation.job_id) atRisk.add(violation.job_id);
  const activeEmergencies = snapshot.jobs.filter(
    (j) => j.emergency && j.status !== "completed" && j.status !== "cancelled",
  ).length;
  return (
    <div
      className="operational-strip"
      data-testid="metrics-strip"
      aria-label="Current approved operations"
    >
      <div data-testid="kpi-available">
        <Users aria-hidden />
        <span>
          Available
          <strong>
            {available}
            <small> / {snapshot.technicians.length} on shift</small>
          </strong>
        </span>
      </div>
      <div data-testid="kpi-scheduled">
        <ClipboardList aria-hidden />
        <span>
          Scheduled
          <strong>
            {snapshot.schedule.assignments.length}
            <small> · {snapshot.metrics.unassigned_jobs} unassigned</small>
          </strong>
        </span>
      </div>
      <div data-testid="kpi-risk">
        <AlertTriangle aria-hidden />
        <span>
          <Tooltip content="Unique jobs that are unassigned, have a future start after a promised time or emergency deadline, or have a validator violation. This is observed schedule risk, not a forecast.">
            <button className="metric-definition">At risk</button>
          </Tooltip>
          <strong className={atRisk.size ? "metric-warning" : ""}>
            {atRisk.size}
            <small> appointments</small>
          </strong>
        </span>
      </div>
      <div data-testid="kpi-emergencies">
        <Siren aria-hidden />
        <span>
          Emergencies
          <strong className={activeEmergencies ? "metric-emergency" : ""}>
            {activeEmergencies}
            <small>
              {pending ? " · 1 pending review" : " · no pending review"}
            </small>
          </strong>
        </span>
      </div>
      <Tooltip
        content={
          snapshot.validation.valid
            ? "The committed schedule passed independent backend validation."
            : "The committed schedule has constraint violations; inspect the details before approving work."
        }
      >
        <span
          className="strip-validation"
          tabIndex={0}
          aria-label={
            snapshot.validation.valid
              ? "Schedule checked"
              : "Schedule needs review"
          }
        >
          <ShieldCheck size={14} aria-hidden />
          <span>{snapshot.validation.valid ? "Checked" : "Needs review"}</span>
          <small className="tabular" data-testid="revision">
            rev {snapshot.revision}
          </small>
        </span>
      </Tooltip>
    </div>
  );
}
