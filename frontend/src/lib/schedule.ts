import type { Assignment, Change, Job, Proposal, Snapshot, Technician } from "@/api/types";

export interface Indexed {
  snap: Snapshot;
  jobs: Map<string, Job>;
  techs: Map<string, Technician>;
  byJob: Map<string, Assignment>;
  routes: Map<string, Assignment[]>;
}

export function index(snap: Snapshot): Indexed {
  const routes = new Map<string, Assignment[]>();
  for (const t of snap.technicians) routes.set(t.id, []);
  for (const a of snap.schedule.assignments) {
    if (!routes.has(a.technician_id)) routes.set(a.technician_id, []);
    routes.get(a.technician_id)!.push(a);
  }
  for (const r of routes.values()) r.sort((a, b) => a.sequence - b.sequence);
  return {
    snap,
    jobs: new Map(snap.jobs.map((j) => [j.id, j])),
    techs: new Map(snap.technicians.map((t) => [t.id, t])),
    byJob: new Map(snap.schedule.assignments.map((a) => [a.job_id, a])),
    routes,
  };
}

export function changesByJob(p: Proposal | null): Map<string, Change> {
  return new Map((p?.status === "ready" ? p.changes : []).map((c) => [c.job_id, c]));
}

/** Time axis: the shift day, widened if any work falls outside it. */
export function timeDomain(snap: Snapshot): [number, number] {
  let lo = Math.min(...snap.technicians.map((t) => t.shift_start_min));
  let hi = Math.max(...snap.technicians.map((t) => t.shift_end_min));
  for (const a of snap.schedule.assignments) {
    lo = Math.min(lo, a.start_min);
    hi = Math.max(hi, a.end_min);
  }
  return [Math.floor(lo / 60) * 60, Math.ceil(hi / 60) * 60];
}

export const skillLabel: Record<string, string> = { hvac: "HVAC", plumbing: "Plumbing", electrical: "Electrical" };
export const skillText = (k: string) => skillLabel[k] ?? k;
