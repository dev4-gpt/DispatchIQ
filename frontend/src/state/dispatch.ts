import type { Proposal, Snapshot, Strategy } from "@/api/types";

export type View = "baseline" | "committed" | "proposed";
export type Busy =
  | null
  | "loading"
  | "previewing"
  | "committing"
  | "rejecting"
  | "resetting";

export interface DispatchState {
  snapshot: Snapshot | null; // last committed snapshot from the server
  baseline: Snapshot | null; // snapshot at load/reset time, for the "before" view
  proposal: Proposal | null;
  proposalStrategy: Strategy | null; // strategy the dispatcher requested for the open proposal
  proposalStale: string | null; // reason the open proposal can no longer be approved
  view: View;
  selectedTech: string | null;
  selectedJob: string | null;
  inspectorOpen: boolean;
  busy: Busy;
  error: {
    message: string;
    scope: "load" | "preview" | "commit" | "reject" | "reset";
  } | null;
  announce: string;
}

export const initialState: DispatchState = {
  snapshot: null,
  baseline: null,
  proposal: null,
  proposalStrategy: null,
  proposalStale: null,
  view: "committed",
  selectedTech: null,
  selectedJob: null,
  inspectorOpen: false,
  busy: "loading",
  error: null,
  announce: "",
};

export type Action =
  | { type: "busy"; busy: Busy }
  | {
      type: "loaded";
      snapshot: Snapshot;
      resetBaseline: boolean;
      announce?: string;
    }
  | { type: "proposal"; proposal: Proposal; strategy: Strategy }
  | { type: "committed"; snapshot: Snapshot }
  | { type: "rejected" }
  | { type: "stale"; reason: string }
  | {
      type: "error";
      scope: NonNullable<DispatchState["error"]>["scope"];
      message: string;
    }
  | { type: "clearError" }
  | { type: "view"; view: View }
  | { type: "selectTech"; id: string | null }
  | { type: "selectJob"; id: string | null }
  | { type: "closeInspector" }
  | { type: "openInspector" };

export function reducer(s: DispatchState, a: Action): DispatchState {
  switch (a.type) {
    case "busy":
      return { ...s, busy: a.busy, error: a.busy ? null : s.error };
    case "loaded":
      return {
        ...s,
        snapshot: a.snapshot,
        baseline: a.resetBaseline || !s.baseline ? a.snapshot : s.baseline,
        proposal: a.resetBaseline ? null : s.proposal,
        proposalStale: a.resetBaseline
          ? null
          : s.proposal &&
              (s.proposal.scenario_epoch !== a.snapshot.scenario_epoch ||
                s.proposal.base_revision !== a.snapshot.revision)
            ? "The approved schedule changed. Preview this event again."
            : s.proposalStale,
        selectedJob: a.resetBaseline ? null : s.selectedJob,
        selectedTech: a.resetBaseline ? null : s.selectedTech,
        inspectorOpen: a.resetBaseline ? false : s.inspectorOpen,
        view: a.resetBaseline ? "committed" : s.view,
        busy: null,
        error: null,
        announce:
          a.announce ?? `Loaded schedule revision ${a.snapshot.revision}.`,
      };
    case "proposal": {
      const p = a.proposal;
      const emergencyId = p.event?.type === "emergency" ? p.event.job.id : null;
      return {
        ...s,
        proposal: p,
        proposalStrategy: a.strategy,
        proposalStale: null,
        busy: null,
        error: null,
        view: p.status === "ready" ? "proposed" : "committed",
        selectedJob: emergencyId ?? s.selectedJob,
        selectedTech: emergencyId
          ? (p.proposed_snapshot?.schedule.assignments.find(
              (a) => a.job_id === emergencyId,
            )?.technician_id ?? null)
          : s.selectedTech,
        inspectorOpen: true,
        announce:
          p.status === "ready"
            ? `Proposal ready with ${p.changes.length} change(s). Review before approving.`
            : p.status === "no_feasible_plan"
              ? "No feasible plan found. The committed schedule is unchanged."
              : "Optimization failed. The committed schedule is unchanged.",
      };
    }
    case "committed":
      return {
        ...s,
        snapshot: a.snapshot,
        proposal: null,
        proposalStale: null,
        view: "committed",
        busy: null,
        error: null,
        announce: `Approved. Schedule is now revision ${a.snapshot.revision}.`,
      };
    case "rejected":
      return {
        ...s,
        proposal: null,
        proposalStale: null,
        selectedJob: null,
        inspectorOpen: false,
        view: "committed",
        busy: null,
        error: null,
        announce: "Proposal rejected. Committed schedule unchanged.",
      };
    case "stale":
      return { ...s, proposalStale: a.reason, busy: null, announce: a.reason };
    case "error":
      return {
        ...s,
        busy: null,
        error: { scope: a.scope, message: a.message },
        announce: a.message,
      };
    case "clearError":
      return { ...s, error: null };
    case "view":
      return { ...s, view: a.view };
    case "selectTech":
      return {
        ...s,
        selectedTech: a.id === s.selectedTech ? null : a.id,
        selectedJob: null,
        inspectorOpen: a.id !== null && a.id !== s.selectedTech,
      };
    case "selectJob":
      return {
        ...s,
        selectedJob: a.id,
        selectedTech:
          (a.id &&
            (
              s.proposal?.proposed_snapshot ?? s.snapshot
            )?.schedule.assignments.find((x) => x.job_id === a.id)
              ?.technician_id) ||
          s.selectedTech,
        inspectorOpen: a.id !== null || s.inspectorOpen,
      };
    case "openInspector":
      return { ...s, inspectorOpen: true };
    case "closeInspector":
      return { ...s, inspectorOpen: false, selectedJob: null };
  }
}

/** Snapshot to render for the current view; proposed falls back to committed when no ready proposal exists. */
export function visibleSnapshot(s: DispatchState): Snapshot | null {
  if (s.view === "baseline") return s.baseline ?? s.snapshot;
  if (s.view === "proposed" && s.proposal?.proposed_snapshot)
    return s.proposal.proposed_snapshot;
  return s.snapshot;
}

export const hhmm = (min: number) =>
  `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
