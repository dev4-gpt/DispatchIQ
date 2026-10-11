import { useEffect, useRef } from "react";
import {
  AlertTriangle,
  ArrowRightLeft,
  Check,
  Clock,
  Lock,
  Radio,
  Siren,
} from "lucide-react";
import type { Change } from "@/api/types";
import { hhmm } from "@/state/dispatch";
import { type Indexed, skillText, timeDomain } from "@/lib/schedule";
import { cn } from "@/lib/utils";

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

const NAME_COL = 144;

export function ScheduleBoard({
  view,
  committed,
  changes,
  showChanges,
  selectedTech,
  selectedJob,
  onSelectTech,
  onSelectJob,
}: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scroller.current;
    if (!el || el.clientWidth >= el.scrollWidth) return;
    const [start, end] = timeDomain(view.snap);
    el.scrollLeft = Math.max(
      0,
      NAME_COL +
        ((view.snap.now_min - start) / (end - start)) *
          (el.scrollWidth - NAME_COL) -
        el.clientWidth * 0.65,
    );
  }, [view.snap.scenario_epoch]);
  const [lo, hi] = timeDomain(view.snap);
  const span = hi - lo;
  const pct = (m: number) => `${((m - lo) / span) * 100}%`;
  const hours = Array.from({ length: span / 60 + 1 }, (_, i) => lo + i * 60);
  const now = view.snap.now_min;
  const unassigned = view.snap.schedule.unassigned_job_ids;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        ref={scroller}
        className="min-h-0 flex-1 overflow-auto"
        role="region"
        aria-label="Technician schedule timeline"
        tabIndex={0}
      >
        <div className="min-w-[950px]">
          {/* axis */}
          <div className="sticky top-0 z-30 flex border-b border-line bg-panel">
            <div
              className="sticky left-0 z-30 flex shrink-0 items-center border-r border-line bg-panel px-3 text-[10px] text-muted"
              style={{ width: NAME_COL }}
            >
              TECHNICIAN
            </div>
            <div className="relative h-7 flex-1">
              {hours.map((h, i) => (
                <span
                  key={h}
                  className="tabular absolute top-1.5 text-[10px] text-muted"
                  style={{
                    left: pct(h),
                    transform:
                      i === 0
                        ? "translateX(6px)"
                        : i === hours.length - 1
                          ? "translateX(calc(-100% - 6px))"
                          : "translateX(-50%)",
                  }}
                >
                  {hhmm(h)}
                </span>
              ))}
            </div>
          </div>
          {view.snap.technicians.map((t) => {
            const route = view.routes.get(t.id) ?? [];
            const sel = selectedTech === t.id;
            return (
              <div
                key={t.id}
                className={cn(
                  "flex border-b border-line/70",
                  sel && "bg-committed-soft/40",
                )}
                data-testid={`row-${t.id}`}
              >
                <button
                  className={cn(
                    "sticky left-0 z-20 flex shrink-0 flex-col items-start justify-center border-r border-line bg-panel px-3 text-left hover:bg-canvas",
                    sel && "bg-committed-soft",
                  )}
                  style={{ width: NAME_COL }}
                  onClick={() => onSelectTech(t.id)}
                  data-testid={`tech-${t.id}`}
                  aria-pressed={sel}
                  aria-label={`${t.name}, skills ${t.skills.map(skillText).join(", ")}${t.availability !== "available" ? ", unavailable" : ""}`}
                >
                  <span
                    className={cn(
                      "text-[13px] font-medium",
                      sel && "text-committed",
                    )}
                  >
                    {t.name}
                    {t.availability !== "available" && (
                      <span className="ml-1 text-[11px] text-emergency">
                        (out)
                      </span>
                    )}
                  </span>
                  <span className="text-[9px] text-muted">
                    {t.skills.map(skillText).join(" · ")}
                  </span>
                </button>
                <div className="relative h-[38px] flex-1">
                  {hours.map((h) => (
                    <div
                      key={h}
                      className="absolute inset-y-0 w-px bg-line/60"
                      style={{ left: pct(h) }}
                    />
                  ))}
                  <div
                    className="absolute inset-y-0 bg-canvas/70"
                    style={{
                      left: 0,
                      width: pct(Math.max(lo, t.shift_start_min)),
                    }}
                  />
                  <div
                    className="absolute inset-y-0 right-0 bg-canvas/70"
                    style={{ left: pct(Math.min(hi, t.shift_end_min)) }}
                  />
                  {route.map((a) => {
                    const j = view.jobs.get(a.job_id)!;
                    const ch = showChanges ? changes.get(a.job_id) : undefined;
                    const before = committed.byJob.get(a.job_id);
                    const isSel = selectedJob === a.job_id;
                    const tone = j.emergency
                      ? "bg-emergency text-white border-emergency"
                      : ch
                        ? "bg-proposed-soft text-proposed border-proposed"
                        : j.status === "completed"
                          ? "bg-ok-soft/60 text-ok border-ok/20"
                          : j.status === "in_progress"
                            ? "bg-committed text-white border-committed"
                            : "bg-committed-soft text-committed border-committed/40";
                    const label =
                      `${j.id} ${j.customer.name}, ${hhmm(a.start_min)}–${hhmm(a.end_min)}` +
                      `, ${j.status.replace("_", " ")}` +
                      (a.frozen || j.locked ? ", locked" : "") +
                      (j.emergency ? ", emergency" : "") +
                      (ch
                        ? `, ${ch.kind}${ch.before ? ` from ${committed.techs.get(ch.before.technician_id)?.name ?? ch.before.technician_id} ${hhmm(ch.before.start_min)}` : ""}`
                        : "");
                    return (
                      <button
                        key={a.job_id}
                        data-testid={`bar-${a.job_id}`}
                        data-change={ch?.kind ?? ""}
                        onClick={() => onSelectJob(a.job_id)}
                        title={label}
                        aria-label={label}
                        className={cn(
                          "absolute top-1 flex h-[29px] items-center gap-1 overflow-hidden rounded-[5px] border px-1.5 text-[10px] font-medium leading-tight",
                          tone,
                          isSel && "ring-2 ring-ink ring-offset-1",
                          ch && "border-dashed",
                        )}
                        style={{
                          left: pct(a.start_min),
                          width: `max(${((a.end_min - a.start_min) / span) * 100}%, 26px)`,
                        }}
                      >
                        {j.status === "completed" && (
                          <Check className="size-3 shrink-0" aria-hidden />
                        )}
                        {j.status === "in_progress" && (
                          <Radio className="size-3 shrink-0" aria-hidden />
                        )}
                        {(j.locked || a.frozen) &&
                          j.status !== "completed" &&
                          j.status !== "in_progress" && (
                            <Lock className="size-3 shrink-0" aria-hidden />
                          )}
                        {j.emergency && (
                          <Siren className="size-3 shrink-0" aria-hidden />
                        )}
                        {ch?.kind === "reassigned" && (
                          <ArrowRightLeft
                            className="size-3 shrink-0"
                            aria-hidden
                          />
                        )}
                        {ch?.kind === "shifted" && (
                          <Clock className="size-3 shrink-0" aria-hidden />
                        )}
                        <span className="shrink-0 tabular">{j.id}</span>
                        {!ch && (
                          <span className="truncate font-normal opacity-80">
                            {j.customer.name}
                          </span>
                        )}
                        {ch && before && ch.kind === "shifted" && (
                          <span className="tabular shrink-0 text-[10px] font-normal">
                            {a.start_min >= before.start_min ? "+" : ""}
                            {a.start_min - before.start_min}m
                          </span>
                        )}
                      </button>
                    );
                  })}
                  {now >= lo && now <= hi && (
                    <div
                      className="pointer-events-none absolute inset-y-0 w-px bg-ink/55"
                      style={{ left: pct(now) }}
                      aria-hidden
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-2 text-[10px]">
        {unassigned.length ? (
          <>
            <AlertTriangle className="size-3.5 text-proposed" aria-hidden />
            <span className="font-medium">
              Unassigned ({unassigned.length}):
            </span>
            {unassigned.map((id) => (
              <button
                key={id}
                onClick={() => onSelectJob(id)}
                className="tabular rounded border border-proposed/40 bg-proposed-soft px-1.5 text-proposed"
              >
                {id}
              </button>
            ))}
          </>
        ) : (
          <span className="text-muted">All jobs assigned</span>
        )}
        <span className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
          <span className="flex items-center gap-1">
            <Check className="size-3 text-ok" aria-hidden /> Complete
          </span>
          <span className="flex items-center gap-1">
            <Radio className="size-3 text-committed" aria-hidden /> In progress
          </span>
          {showChanges && (
            <span className="flex items-center gap-1">
              <Clock className="size-3 text-proposed" /> Changed
            </span>
          )}
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-px bg-ink/55" /> Now {hhmm(now)}
          </span>
        </span>
      </div>
    </div>
  );
}
