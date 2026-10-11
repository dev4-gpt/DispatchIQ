import { AlertTriangle, ArrowRightLeft, Clock, Lock, Siren } from "lucide-react";
import type { Change } from "@/api/types";
import { hhmm } from "@/state/dispatch";
import { type Indexed, skillText, timeDomain } from "@/lib/schedule";
import { cn } from "@/lib/utils";
import { WORKER, workerType } from "@/lib/workers";

interface Props {
  view: Indexed;
  committed: Indexed;
  changes: Map<string, Change>;
  showChanges: boolean;
  selectedTech: string | null;
  selectedJob: string | null;
  onSelectTech: (id: string) => void;
  onSelectJob: (id: string) => void;
}

const NAME_COL = 168;

export function ScheduleBoard({ view, committed, changes, showChanges, selectedTech, selectedJob, onSelectTech, onSelectJob }: Props) {
  const [lo, hi] = timeDomain(view.snap);
  const span = hi - lo;
  const pct = (m: number) => `${((m - lo) / span) * 100}%`;
  const hours = Array.from({ length: span / 60 + 1 }, (_, i) => lo + i * 60);
  const now = view.snap.now_min;
  const unassigned = view.snap.schedule.unassigned_job_ids;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto" role="region" aria-label="Technician schedule timeline" tabIndex={0}>
        <div className="min-w-[760px]">
          {/* axis */}
          <div className="sticky top-0 z-10 flex border-b border-line bg-panel" style={{ paddingLeft: NAME_COL }}>
            <div className="relative h-7 flex-1">
              {hours.map((h) => (
                <span key={h} className="tabular absolute top-1.5 -translate-x-1/2 text-[11px] text-muted" style={{ left: pct(h) }}>{hhmm(h)}</span>
              ))}
            </div>
          </div>
          {view.snap.technicians.map((t) => {
            const route = view.routes.get(t.id) ?? [];
            const sel = selectedTech === t.id;
            return (
              <div key={t.id} className={cn("flex border-b border-line/70", sel && "bg-committed-soft/40")} data-testid={`row-${t.id}`}>
                <button
                  className="flex shrink-0 flex-col items-start gap-1 border-r border-line px-3 py-1.5 text-left hover:bg-canvas"
                  style={{ width: NAME_COL }}
                  onClick={() => onSelectTech(t.id)}
                  aria-pressed={sel}
                  aria-label={`${t.name}, ${WORKER[workerType(t)].label}, skills ${t.skills.map(skillText).join(", ")}${t.availability !== "available" ? ", unavailable" : ""}`}
                >
                  <span className={cn("flex items-center gap-1 text-[13px] font-medium", sel && "text-committed")}>
                    {(() => { const I = WORKER[workerType(t)].icon; return <I className="size-3.5 shrink-0 text-muted" aria-hidden />; })()}
                    {t.name}
                    {t.availability !== "available" && <span className="ml-1 text-[11px] text-emergency">(out)</span>}</span>
                  <span className="flex flex-wrap gap-1">
                    {t.skills.map((k) => (
                      <span key={k} className="rounded bg-canvas px-1 text-[10px] text-muted">{skillText(k)}</span>
                    ))}
                  </span>
                </button>
                <div className="relative h-[46px] flex-1">
                  {hours.map((h) => <div key={h} className="absolute inset-y-0 w-px bg-line/60" style={{ left: pct(h) }} />)}
                  <div className="absolute inset-y-0 bg-canvas/70" style={{ left: 0, width: pct(Math.max(lo, t.shift_start_min)) }} />
                  <div className="absolute inset-y-0 right-0 bg-canvas/70" style={{ left: pct(Math.min(hi, t.shift_end_min)) }} />
                  {route.map((a) => {
                    const j = view.jobs.get(a.job_id)!;
                    const ch = showChanges ? changes.get(a.job_id) : undefined;
                    const before = committed.byJob.get(a.job_id);
                    const isSel = selectedJob === a.job_id;
                    const tone = j.emergency
                      ? "bg-emergency text-white border-emergency"
                      : ch
                        ? "bg-proposed-soft text-proposed border-proposed"
                        : a.frozen
                          ? "bg-frozen/60 text-ink/70 border-frozen"
                          : "bg-committed-soft text-committed border-committed/40";
                    const label = `${j.id} ${j.customer.name}, ${hhmm(a.start_min)}–${hhmm(a.end_min)}` +
                      (a.frozen ? ", started (locked)" : "") + (j.emergency ? ", emergency" : "") +
                      (ch ? `, ${ch.kind}${ch.before ? ` from ${committed.techs.get(ch.before.technician_id)?.name ?? ch.before.technician_id} ${hhmm(ch.before.start_min)}` : ""}` : "");
                    return (
                      <button
                        key={a.job_id}
                        data-testid={`bar-${a.job_id}`}
                        data-change={ch?.kind ?? ""}
                        onClick={() => onSelectJob(a.job_id)}
                        title={label}
                        aria-label={label}
                        className={cn("absolute top-1.5 flex h-[34px] items-center gap-1 overflow-hidden rounded-[5px] border px-1.5 text-[11px] font-medium leading-tight",
                          tone, isSel && "ring-2 ring-ink ring-offset-1", ch && "border-dashed")}
                        style={{ left: pct(a.start_min), width: `max(${((a.end_min - a.start_min) / span) * 100}%, 26px)` }}
                      >
                        {a.frozen && <Lock className="size-3 shrink-0" aria-hidden />}
                        {j.emergency && <Siren className="size-3 shrink-0" aria-hidden />}
                        {ch?.kind === "reassigned" && <ArrowRightLeft className="size-3 shrink-0" aria-hidden />}
                        {ch?.kind === "shifted" && <Clock className="size-3 shrink-0" aria-hidden />}
                        <span className="truncate tabular">{j.id}</span>
                        {ch && before && ch.kind === "shifted" && (
                          <span className="tabular truncate text-[10px] font-normal">+{a.start_min - before.start_min}m</span>
                        )}
                      </button>
                    );
                  })}
                  {now >= lo && now <= hi && (
                    <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-emergency/70" style={{ left: pct(now) }} aria-hidden />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex items-center gap-2 border-t border-line px-3 py-1.5 text-[12px]">
        {unassigned.length ? (
          <>
            <AlertTriangle className="size-3.5 text-proposed" aria-hidden />
            <span className="font-medium">Unassigned ({unassigned.length}):</span>
            {unassigned.map((id) => (
              <button key={id} onClick={() => onSelectJob(id)} className="tabular rounded border border-proposed/40 bg-proposed-soft px-1.5 text-proposed">{id}</button>
            ))}
          </>
        ) : (
          <span className="text-muted">No unassigned work in this view.</span>
        )}
        <span className="ml-auto flex items-center gap-3 text-[11px] text-muted">
          <span className="flex items-center gap-1"><Lock className="size-3" aria-hidden /> started (locked)</span>
          <span className="flex items-center gap-1"><span className="h-2 w-3 rounded-sm border border-dashed border-proposed bg-proposed-soft" /> proposed change</span>
          <span className="flex items-center gap-1"><Siren className="size-3 text-emergency" aria-hidden /> emergency</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-0.5 bg-emergency/70" /> now {hhmm(now)}</span>
        </span>
      </div>
    </div>
  );
}
