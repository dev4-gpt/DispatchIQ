import { Lock, Siren } from "lucide-react";
import type { Assignment, Proposal } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { hhmm } from "@/state/dispatch";
import { type Indexed, skillText } from "@/lib/schedule";

interface Props {
  jobId: string;
  committed: Indexed;
  proposed: Indexed | null;
  proposal: Proposal | null;
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1 text-[12.5px]">
      <dt className="text-muted">{k}</dt>
      <dd className="tabular text-right">{v}</dd>
    </div>
  );
}

function placement(a: Assignment | undefined, idx: Indexed) {
  if (!a) return <span className="text-proposed">Unassigned</span>;
  return `${idx.techs.get(a.technician_id)?.name ?? a.technician_id} · ${hhmm(a.start_min)}–${hhmm(a.end_min)} · ${a.travel_min} min travel`;
}

export function JobInspector({ jobId, committed, proposed, proposal }: Props) {
  const job = proposed?.jobs.get(jobId) ?? committed.jobs.get(jobId) ??
    (proposal?.event?.type === "emergency" && proposal.event.job.id === jobId ? { ...proposal.event.job, status: "unassigned" as const } : undefined);
  if (!job) return <p className="text-[12px] text-muted">Job {jobId} is not in this schedule.</p>;
  const ca = committed.byJob.get(jobId);
  const pa = proposed?.byJob.get(jobId);
  const changed = proposed && (ca?.technician_id !== pa?.technician_id || ca?.start_min !== pa?.start_min);
  const eligibility = job.emergency && proposal?.event?.type === "emergency" && proposal.event.job.id === jobId ? proposal.candidates : null;
  const techSummary = eligibility
    ? [...new Map(eligibility.map((c) => [c.technician_id, c])).values()].map((c) => {
        const all = eligibility.filter((x) => x.technician_id === c.technician_id);
        const ok = all.some((x) => x.valid);
        return { id: c.technician_id, ok, eligible: c.eligible, reason: ok ? "Valid insertion found" : all[0].reasons[0] ?? "No valid slot" };
      })
    : null;

  return (
    <section aria-labelledby="job-h" data-testid="job-inspector" className="space-y-2">
      <div className="space-y-1.5">
        <div>
          <h2 id="job-h" className="flex items-center gap-1.5 text-[15px] font-semibold">
            {job.emergency && <Siren className="size-4 text-emergency" aria-label="Emergency" />}
            <span className="tabular">{job.id}</span> · {job.customer.name}
          </h2>
          <p className="text-[12px] text-muted">{job.customer.site_name}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {job.emergency && <Badge tone="red">Emergency · P{job.priority}</Badge>}
          {!job.emergency && <Badge>Priority {job.priority}</Badge>}
          <Badge tone={job.status === "completed" ? "green" : job.status === "unassigned" ? "amber" : "blue"}>{job.status.replace("_", " ")}</Badge>
          {(ca?.frozen || job.locked) && <Badge><Lock /> {ca?.frozen ? "started" : "locked"}</Badge>}
        </div>
      </div>
      <dl className="divide-y divide-line">
        <Row k="Required skills" v={job.required_skills.map(skillText).join(", ")} />
        <Row k="Start window" v={`${hhmm(job.earliest_start_min)}–${hhmm(job.latest_start_min)}`} />
        <Row k="Must finish by" v={hhmm(job.window_end_min)} />
        {job.deadline_start_min !== null && <Row k="Response deadline" v={hhmm(job.deadline_start_min)} />}
        {job.soft_promised_start_min !== null && <Row k="Promised start (soft)" v={hhmm(job.soft_promised_start_min)} />}
        <Row k="Duration" v={`${job.duration_min} min`} />
        <Row k="Location (grid)" v={`${job.location.x_km}, ${job.location.y_km} km`} />
        <Row k="Committed" v={placement(ca, committed)} />
        {proposed && <Row k="Proposed" v={<span className={changed ? "font-semibold text-proposed" : ""}>{placement(pa, proposed)}</span>} />}
        {proposed && pa && job.emergency && <Row k="Response time" v={`${pa.start_min - job.release_min} min after call`} />}
      </dl>
      {techSummary && (
        <div>
          <h3 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-muted">Technician eligibility</h3>
          <ul className="space-y-0.5 text-[12px]">
            {techSummary.map((t) => (
              <li key={t.id} className="flex justify-between gap-2">
                <span>{committed.techs.get(t.id)?.name ?? t.id}</span>
                <span className={t.ok ? "text-ok" : "text-muted"}>{t.ok ? "✓ " : "✕ "}{t.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
