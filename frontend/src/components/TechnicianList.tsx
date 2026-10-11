import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { type Indexed, skillText } from "@/lib/schedule";
import { TYPE_ORDER, WORKER, workerType } from "@/lib/workers";
import { hhmm } from "@/state/dispatch";

interface Props {
  view: Indexed;
  selectedTech: string | null;
  onSelectTech: (id: string) => void;
}

/** Workers grouped by kind: people, robots, AI agents. */
export function TechnicianList({ view, selectedTech, onSelectTech }: Props) {
  const now = view.snap.now_min;
  return (
    <div className="space-y-3">
      {TYPE_ORDER.map((type) => {
        const group = view.snap.technicians.filter((t) => workerType(t) === type);
        if (!group.length) return null;
        const Icon = WORKER[type].icon;
        return (
          <section key={type} aria-label={WORKER[type].plural}>
            <h3 className="flex items-center gap-1.5 px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
              <Icon className="size-3.5" aria-hidden /> {WORKER[type].plural} · {group.length}
            </h3>
            <ul className="space-y-0.5">
              {group.map((t) => {
                const route = view.routes.get(t.id) ?? [];
                const current = route.find((a) => a.start_min <= now && now < a.end_min);
                const next = route.find((a) => a.start_min > now);
                const sel = selectedTech === t.id;
                const cowork = t.certifications?.includes("robot_cowork");
                return (
                  <li key={t.id}>
                    <button onClick={() => onSelectTech(t.id)} aria-pressed={sel} data-testid={`tech-${t.id}`}
                      className={cn("w-full rounded-md px-2 py-1.5 text-left hover:bg-canvas", sel && "bg-committed-soft hover:bg-committed-soft")}>
                      <div className="flex items-center justify-between gap-1">
                        <span className={cn("flex items-center gap-1 text-[13px] font-medium", sel && "text-committed")}>
                          {t.name}
                          {cowork && <ShieldCheck className="size-3.5 text-ok" aria-label="Robot co-work certified" />}
                        </span>
                        <span className={cn("size-2 rounded-full", t.availability === "available" ? "bg-ok" : "bg-emergency")}
                          aria-label={t.availability} role="img" />
                      </div>
                      <div className="tabular mt-0.5 truncate text-[11px] text-muted">
                        {t.skills.map(skillText).join(" · ")} · {current ? `on ${current.job_id}` : next ? `next ${next.job_id} ${hhmm(next.start_min)}` : "free"}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
