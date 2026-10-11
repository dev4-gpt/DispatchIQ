import { useState } from "react";
import { Loader2, RotateCcw, Siren } from "lucide-react";
import type { EmergencyEvent, Snapshot, Strategy } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { hhmm, type Busy } from "@/state/dispatch";
import { skillText } from "@/lib/schedule";

interface Props {
  snapshot: Snapshot | null;
  busy: Busy;
  hasOpenProposal: boolean;
  onPreview: (e: EmergencyEvent, strategy: Strategy) => void;
  onReset: () => void;
}

const PRESETS = [
  { label: "No heat at a clinic", name: "Civic Clinic", site: "Plant room", skill: "hvac", x: 8, y: 6, duration: 45, deadline: 60 },
  { label: "Power loss at a bakery", name: "Rise Bakery", site: "Kitchen", skill: "electrical", x: 17, y: 14, duration: 60, deadline: 45 },
  { label: "Burst pipe", name: "Maple Apartments", site: "Basement", skill: "plumbing", x: 12, y: 14, duration: 60, deadline: 75 },
  { label: "Elevator fault (no qualified tech)", name: "Hilltop Offices", site: "Lift shaft", skill: "elevator", x: 15, y: 5, duration: 60, deadline: 45 },
];

export function ScenarioControls({ snapshot, busy, hasOpenProposal, onPreview, onReset }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(PRESETS[0]);
  const [strategy, setStrategy] = useState<Strategy>("stable_insertion");
  const skills = [...new Set([...(snapshot?.technicians.flatMap((t) => t.skills) ?? []), "elevator"])];

  const nextId = () => {
    const ids = new Set(snapshot?.jobs.map((j) => j.id));
    let n = (snapshot?.jobs.filter((j) => j.emergency).length ?? 0) + 1;
    while (ids.has(`E${String(n).padStart(2, "0")}`)) n++;
    return `E${String(n).padStart(2, "0")}`;
  };

  const submit = () => {
    if (!snapshot) return;
    const now = snapshot.now_min;
    const id = nextId();
    onPreview({
      type: "emergency", at_min: now,
      job: {
        id, customer: { id: `C-${id}`, name: form.name, site_name: form.site },
        location: { x_km: form.x, y_km: form.y, latitude: null, longitude: null },
        required_skills: [form.skill], priority: 5, duration_min: form.duration,
        earliest_start_min: now, latest_start_min: now + form.deadline, window_end_min: now + form.deadline + form.duration + 120,
        soft_promised_start_min: null, deadline_start_min: now + form.deadline, release_min: now, emergency: true, locked: false,
      },
    }, strategy);
    setOpen(false);
  };

  const field = "mt-1 h-8 w-full rounded-md border border-line bg-panel px-2 text-[13px]";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" onClick={onReset} disabled={busy !== null || !snapshot} data-testid="reset">
        {busy === "resetting" ? <Loader2 className="animate-spin" /> : <RotateCcw />} Reset
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <Button size="sm" variant="danger" onClick={() => setOpen(true)} disabled={busy !== null || !snapshot || hasOpenProposal}
          data-testid="introduce-emergency" title={hasOpenProposal ? "Approve or reject the open proposal first" : undefined}>
          {busy === "previewing" ? <Loader2 className="animate-spin" /> : <Siren />} Introduce emergency
        </Button>
        <DialogContent title="Introduce an emergency" description={snapshot ? `Call received now (${hhmm(snapshot.now_min)}). The committed schedule changes only after you approve.` : undefined}>
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Presets">
              {PRESETS.map((p) => (
                <Button key={p.label} size="sm" variant={form.label === p.label ? "primary" : "outline"} onClick={() => setForm(p)}>{p.label}</Button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              <label>Customer<input className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value, label: "" })} /></label>
              <label>Site<input className={field} value={form.site} onChange={(e) => setForm({ ...form, site: e.target.value, label: "" })} /></label>
              <label>Required skill
                <select className={field} value={form.skill} onChange={(e) => setForm({ ...form, skill: e.target.value, label: "" })}>
                  {skills.map((s) => <option key={s} value={s}>{skillText(s)}</option>)}
                </select>
              </label>
              <label>Duration (min)<input type="number" min={15} step={15} className={field} value={form.duration}
                onChange={(e) => setForm({ ...form, duration: Number(e.target.value), label: "" })} /></label>
              <label>Grid x (km)<input type="number" min={0} max={30} className={field} value={form.x} onChange={(e) => setForm({ ...form, x: Number(e.target.value), label: "" })} /></label>
              <label>Grid y (km)<input type="number" min={0} max={30} className={field} value={form.y} onChange={(e) => setForm({ ...form, y: Number(e.target.value), label: "" })} /></label>
              <label>Proposal strategy
                <select className={field} value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)} data-testid="strategy">
                  <option value="stable_insertion">Least disruption</option>
                  <option value="first_feasible">First feasible</option>
                </select>
              </label>
              <label>Respond within (min)<input type="number" min={15} step={15} className={field} value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: Number(e.target.value), label: "" })} /></label>
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="danger" onClick={submit} data-testid="preview-emergency"><Siren /> Preview re-plan</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
