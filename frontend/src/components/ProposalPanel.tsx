import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Siren,
  XCircle,
} from "lucide-react";
import type { ComparisonEntry, Proposal, Strategy } from "@/api/types";
import { ScheduleComparison } from "@/components/ScheduleComparison";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { hhmm, type Busy } from "@/state/dispatch";
import type { Indexed } from "@/lib/schedule";

interface Props {
  proposal: Proposal;
  strategy: Strategy | null;
  committed: Indexed;
  stale: string | null;
  busy: Busy;
  onApprove: () => void;
  onReject: () => void;
  onRefresh: () => void;
  onSelectJob: (id: string) => void;
}
const strategyName = (s: string) =>
  s === "stable_insertion" ? "Least disruption" : "First feasible";

export function ProposalPanel({
  proposal: p,
  strategy,
  committed,
  stale,
  busy,
  onApprove,
  onReject,
  onRefresh,
  onSelectJob,
}: Props) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [p.proposal_id]);
  const expired = now >= Date.parse(p.expires_at_utc);
  const outdated =
    stale ||
    (expired
      ? "This proposal expired. Refresh and preview the event again."
      : null);
  const ready =
    p.status === "ready" && !!p.proposed_snapshot && p.validation.valid;
  const canApprove = ready && !outdated && busy === null;
  const event = p.event?.type === "emergency" ? p.event.job : null;
  const assignment = event
    ? p.proposed_snapshot?.schedule.assignments.find(
        (a) => a.job_id === event.id,
      )
    : null;
  const emergency = event
    ? p.proposed_snapshot?.metrics.emergencies.find(
        (e) => e.job_id === event.id,
      )
    : null;
  const valid = p.candidates.filter((c) => c.valid && c.ranking);
  const rejected = p.candidates.filter((c) => !c.valid);
  const selected = p.comparison.find((c) => c.strategy === strategy);
  const diff = selected?.diff_metrics;
  const selectedCandidate = p.candidates.find(
    (c) => c.id === p.selected_candidate_id,
  );
  const assignedTech = committed.techs.get(assignment?.technician_id ?? "");
  return (
    <section
      className="proposal-review"
      data-testid="proposal-panel"
      aria-labelledby="proposal-h"
    >
      <div className="proposal-status">
        {outdated ? (
          <Badge tone="amber">
            <ShieldAlert />
            Outdated
          </Badge>
        ) : ready ? (
          <Badge tone="green">
            <CheckCircle2 />
            Ready to review
          </Badge>
        ) : (
          <Badge tone="red">
            <XCircle />
            {p.status === "no_feasible_plan" ? "No feasible plan" : "Failed"}
          </Badge>
        )}
        <span>Unapproved proposal</span>
      </div>
      <div className="emergency-summary">
        <span className="emergency-icon">
          <Siren size={18} />
        </span>
        <div>
          <h2 id="proposal-h">
            {event?.customer.name ?? "Schedule adjustment"}
          </h2>
          <p>
            {event
              ? `${event.id} · ${event.customer.site_name}`
              : "Review before updating the day"}
          </p>
        </div>
      </div>
      {event && (
        <dl className="proposal-facts">
          <div>
            <dt>Priority</dt>
            <dd>
              {event.priority === 5 ? "Critical" : `Priority ${event.priority}`}
            </dd>
          </div>
          <div>
            <dt>Synthetic location</dt>
            <dd className="tabular">
              ({event.location.x_km}, {event.location.y_km}) km
            </dd>
          </div>
          <div>
            <dt>Response deadline</dt>
            <dd>
              {event.deadline_start_min !== null
                ? hhmm(event.deadline_start_min)
                : "Not specified"}
            </dd>
          </div>
          <div>
            <dt>Required skills</dt>
            <dd>{event.required_skills.join(", ").toUpperCase()}</dd>
          </div>
          {assignment && (
            <>
              <div>
                <dt>Recommended technician</dt>
                <dd>
                  {committed.techs.get(assignment.technician_id)?.name ??
                    assignment.technician_id}
                  {assignedTech &&
                    event.required_skills.every((skill) =>
                      assignedTech.skills.includes(skill),
                    ) && (
                      <span className="deadline-met">
                        <CheckCircle2 size={12} /> Required skills matched
                      </span>
                    )}
                </dd>
              </div>
              <div>
                <dt>Estimated start</dt>
                <dd>
                  {hhmm(assignment.start_min)}
                  {emergency?.deadline_met && (
                    <span className="deadline-met">
                      <CheckCircle2 size={12} />
                      Within deadline
                    </span>
                  )}
                </dd>
              </div>
            </>
          )}
        </dl>
      )}
      {outdated && (
        <div
          role="alert"
          className="rounded-md bg-proposed-soft p-3 text-[12px] text-proposed"
        >
          {outdated}
          <Button size="sm" className="mt-2" onClick={onRefresh}>
            <RefreshCw />
            Refresh committed schedule
          </Button>
        </div>
      )}
      <ScheduleComparison
        key={p.proposal_id}
        proposal={p}
        committed={committed}
        onSelectJob={onSelectJob}
      />
      <details className="review-disclosure" open={!ready}>
        <summary>Why this recommendation</summary>
        {diff && (
          <div className="proposal-impact">
            <div>
              <strong>{diff.changed_existing_jobs}</strong>
              <span>existing jobs changed</span>
            </div>
            <div>
              <strong>
                {diff.absolute_start_shift_min}
                <small> min</small>
              </strong>
              <span>total start shift</span>
            </div>
            {emergency && (
              <div>
                <strong>
                  {emergency.response_min ?? "—"}
                  <small> min</small>
                </strong>
                <span>emergency response</span>
              </div>
            )}
          </div>
        )}
        <p data-testid="proposal-explanation">{p.explanation}</p>
        {selectedCandidate?.ranking && (
          <p data-testid="travel-impact">
            Future travel change:{" "}
            {selectedCandidate.ranking.added_travel_min > 0 ? "+" : ""}
            {selectedCandidate.ranking.added_travel_min} min, as measured by the
            backend for this candidate.
          </p>
        )}
        {!ready && (
          <p>
            {p.search.feasibility_proven_impossible
              ? "A necessary scheduling condition fails for this event."
              : "No feasible plan was found under this search. This does not prove none exists."}{" "}
            The approved schedule is unchanged.
          </p>
        )}
      </details>
      {p.comparison.length > 0 && (
        <details className="review-disclosure">
          <summary>Compare evaluated approaches</summary>
          <Comparison
            rows={p.comparison}
            strategy={strategy}
            eventId={event?.id}
          />
          <p>
            Both approaches evaluate the same event and approved schedule.
            Travel covers future work.
          </p>
        </details>
      )}
      <details className="review-disclosure">
        <summary>
          Technician options · {valid.length} valid, {rejected.length} rejected
        </summary>
        <div className="candidate-options">
          {valid.map((c) => (
            <div key={c.id}>
              <strong>
                {committed.techs.get(c.technician_id)?.name ?? c.technician_id}
                {c.id === p.selected_candidate_id ? " · selected" : ""}
              </strong>
              <span>
                {c.emergency_start_min !== null
                  ? hhmm(c.emergency_start_min)
                  : "—"}{" "}
                · {c.ranking!.changed_existing_jobs} changed ·{" "}
                {c.ranking!.absolute_start_shift_min} min shift
              </span>
            </div>
          ))}
          {rejected.map((c) => (
            <div key={c.id}>
              <strong>
                {committed.techs.get(c.technician_id)?.name ?? c.technician_id}
              </strong>
              <span>{c.reasons.join("; ")}</span>
            </div>
          ))}
        </div>
      </details>
      <div className="validation-summary">
        {p.validation.valid && ready ? (
          <span>
            <CheckCircle2 size={14} />
            Schedule independently checked
          </span>
        ) : p.validation.violations.length ? (
          <ul role="alert">
            {p.validation.violations.map((v, i) => (
              <li key={i}>{v.message}</li>
            ))}
          </ul>
        ) : null}
        <small>
          Evaluated in {p.runtime_ms.toFixed(1)} ms ·{" "}
          {p.search.candidates_evaluated} options ·{" "}
          {p.search.termination === "budget_exhausted"
            ? "Search budget reached"
            : "Search complete"}
        </small>
      </div>
      <div className="proposal-decision">
        <Button
          variant="approve"
          disabled={!canApprove}
          onClick={onApprove}
          data-testid="approve"
        >
          {busy === "committing" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <CheckCircle2 />
          )}
          Approve Changes
        </Button>
        <Button
          disabled={busy !== null}
          onClick={onReject}
          data-testid="reject"
        >
          {busy === "rejecting" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <XCircle />
          )}
          {ready && !outdated ? "Reject Proposal" : "Dismiss"}
        </Button>
        <p>
          {outdated
            ? "Outdated proposals cannot be approved."
            : !ready
              ? "Only a validated proposal can be approved."
              : "Approval applies the event and schedule together."}
        </p>
      </div>
    </section>
  );
}
function Comparison({
  rows,
  strategy,
  eventId,
}: {
  rows: ComparisonEntry[];
  strategy: Strategy | null;
  eventId?: string;
}) {
  return (
    <div className="strategy-comparison" data-testid="comparison">
      {rows.map((r) => {
        const response = eventId
          ? r.metrics?.emergencies.find((e) => e.job_id === eventId)
          : undefined;
        return (
          <div key={r.strategy}>
            <h4>
              {strategyName(r.strategy)}
              {r.strategy === strategy && " (proposed)"}
            </h4>
            {r.status === "ready" && r.metrics && r.diff_metrics ? (
              <dl>
                <div>
                  <dt>Jobs changed</dt>
                  <dd>{r.diff_metrics.changed_existing_jobs}</dd>
                </div>
                <div>
                  <dt>Total start shift</dt>
                  <dd>{r.diff_metrics.absolute_start_shift_min} min</dd>
                </div>
                <div>
                  <dt>Emergency response</dt>
                  <dd>{response?.response_min ?? "—"} min</dd>
                </div>
                <div>
                  <dt>Future travel</dt>
                  <dd>{r.metrics.travel_min} min</dd>
                </div>
                <div>
                  <dt>Measured runtime</dt>
                  <dd>{r.runtime_ms.toFixed(1)} ms</dd>
                </div>
              </dl>
            ) : (
              <p>
                {r.status === "no_feasible_plan"
                  ? "No feasible plan found"
                  : "Evaluation failed"}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
