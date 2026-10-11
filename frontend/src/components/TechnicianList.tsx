import { cn } from "@/lib/utils";
import { type Indexed, skillText } from "@/lib/schedule";
import { hhmm } from "@/state/dispatch";

interface Props {
  view: Indexed;
  selectedTech: string | null;
  onSelectTech: (id: string) => void;
  compact?: boolean;
}

export function TechnicianList({ view, selectedTech, onSelectTech, compact }: Props) {
  const now = view.snap.now_min;
  return (
    <ul className="space-y-0.5" aria-label="Technicians">
      {view.snap.technicians.map((t) => {
        const route = view.routes.get(t.id) ?? [];
        const current = route.find((a) => a.start_min <= now && now < a.end_min);
        const next = route.find((a) => a.start_min > now);
        const sel = selectedTech === t.id;
        return (
          <li key={t.id}>
            <button
              onClick={() => onSelectTech(t.id)}
              aria-pressed={sel}
              data-testid={`tech-${t.id}`}
              className={cn("w-full rounded-md px-2 py-1.5 text-left hover:bg-canvas", sel && "bg-committed-soft hover:bg-committed-soft")}
            >
              <div className="flex items-center justify-between gap-1">
                <span className={cn("text-[13px] font-medium", sel && "text-committed")}>{t.name}</span>
                <span className={cn("size-2 rounded-full", t.availability === "available" ? "bg-ok" : "bg-emergency")}
                  aria-label={t.availability} role="img" />
              </div>
              {!compact && (
                <div className="tabular mt-0.5 truncate text-[11px] text-muted">
                  {t.skills.map(skillText).join(" · ")} · {current ? `on ${current.job_id}` : next ? `next ${next.job_id} ${hhmm(next.start_min)}` : "free"}
                </div>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
