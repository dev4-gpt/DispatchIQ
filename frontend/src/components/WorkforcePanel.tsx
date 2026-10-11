import type { Indexed } from "@/lib/schedule";
import { TYPE_ORDER, WORKER, workerType } from "@/lib/workers";

/**
 * Per worker type: availability, work done / in progress / planned today, and utilization of
 * daily capacity. Computed from the schedule shown, so it is a measurement of the plan, not of
 * field telemetry (which this demo does not have).
 */
export function WorkforcePanel({ view }: { view: Indexed }) {
  const now = view.snap.now_min;
  const rows = TYPE_ORDER.map((type) => {
    const workers = view.snap.technicians.filter((t) => workerType(t) === type);
    const ids = new Set(workers.map((t) => t.id));
    const work = view.snap.schedule.assignments.filter((a) => ids.has(a.technician_id));
    const done = work.filter((a) => a.end_min <= now).length;
    const active = work.filter((a) => a.start_min <= now && now < a.end_min).length;
    const planned = work.length - done - active;
    const used = work.reduce((m, a) => m + (a.end_min - a.start_min), 0);
    const cap = workers.reduce((m, t) => m + t.max_service_min, 0);
    return { type, workers, available: workers.filter((t) => t.availability === "available").length, done, active, planned,
      util: cap ? Math.round((100 * used) / cap) : 0 };
  }).filter((r) => r.workers.length);

  return (
    <section aria-labelledby="wf-h" data-testid="workforce">
      <h2 id="wf-h" className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Workforce today</h2>
      <ul className="space-y-1.5 px-2">
        {rows.map((r) => {
          const I = WORKER[r.type].icon;
          return (
            <li key={r.type} data-testid={`wf-${r.type}`} className="text-[12px]">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 font-medium"><I className="size-3.5 text-muted" aria-hidden />{WORKER[r.type].plural}</span>
                <span className="tabular text-[11px] text-muted">{r.available}/{r.workers.length} available</span>
              </div>
              <div className="tabular text-[11px] text-muted">{r.done} done · {r.active} now · {r.planned} next · {r.util}% load</div>
            </li>
          );
        })}
      </ul>
      <p className="px-2 pt-1 text-[10.5px] leading-snug text-muted">From the schedule shown. Field telemetry and robot faults are not modeled yet.</p>
    </section>
  );
}
