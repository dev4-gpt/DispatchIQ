import { ArrowRight, ArrowRightLeft, CheckCircle2, CircleSlash, Clock, Loader2, Plus, RefreshCw, ShieldAlert, XCircle } from "lucide-react";
import type { Change, ComparisonEntry, Proposal, Strategy } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { hhmm, type Busy } from "@/state/dispatch";
import type { Indexed } from "@/lib/schedule";
import { WORKER, workerType } from "@/lib/workers";

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

const KIND = {
  added: { icon: Plus, text: "Added" },
  reassigned: { icon: ArrowRightLeft, text: "Reassigned" },
  shifted: { icon: Clock, text: "Time shifted" },
  unassigned: { icon: CircleSlash, text: "Unassigned" },
} as const;

function Place({ p, idx }: { p: Change["before"]; idx: Indexed }) {
  if (!p) return <span className="text-muted">—</span>;
  return <span className="tabular">{idx.techs.get(p.technician_id)?.name ?? p.technician_id} {hhmm(p.start_min)}</span>;
}

const strategyName = (s: string) => (s === "stable_insertion" ? "Least disruption" : s === "first_feasible" ? "First feasible" : s);

export function ProposalPanel({ proposal: p, strategy, committed, stale, busy, onApprove, onReject, onRefresh, onSelectJob }: Props) {
  const ready = p.status === "ready" && !!p.proposed_snapshot && p.validation.valid;
  const canApprove = ready && !stale && busy === null;
  const evt = p.event?.type === "emergency" ? p.event.job : null;
  const proposedIdx = p.proposed_snapshot ? p.proposed_snapshot : null;
  const validCands = p.candidates.filter((c) => c.valid && c.ranking).sort((a, b) =>
    (a.id === p.selected_candidate_id ? -1 : b.id === p.selected_candidate_id ? 1 : 0));
  const rejected = p.candidates.filter((c) => !c.valid);

  return (
    <section aria-labelledby="proposal-h" className="space-y-3" data-testid="proposal-panel">
      <div className="flex items-start justify-between gap-2 pr-6">
        <div>
          <h2 id="proposal-h" className="text-[15px] font-semibold">Proposed change</h2>
          <p className="text-[12px] text-muted">
            {evt ? <>Emergency <span className="tabular">{evt.id}</span> · {evt.customer.name}</> : "Re-plan"} · base revision {p.base_revision}
          </p>
        </div>
        {stale ? <Badge tone="amber"><ShieldAlert /> Outdated</Badge>
          : p.status === "ready" ? <Badge tone="green"><CheckCircle2 /> Ready to review</Badge>
          : p.status === "no_feasible_plan" ? <Badge tone="red"><XCircle /> No feasible plan</Badge>
          : <Badge tone="red"><XCircle /> Failed</Badge>}
      </div>

      {stale && (
        <div role="alert" className="rounded-md border border-proposed/40 bg-proposed-soft p-2.5 text-[12px] text-proposed">
          {stale} This proposal can no longer be approved.
          <Button size="sm" variant="outline" className="mt-2" onClick={onRefresh}><RefreshCw /> Refresh committed schedule</Button>
        </div>
      )}

      <div className="rounded-md bg-canvas p-2.5 text-[12.5px] leading-relaxed">
        <p data-testid="proposal-explanation">{p.explanation}</p>
        <p className="mt-1.5 text-[11px] text-muted">
          Deterministic explanation built from the evaluated candidates below. No language model was used.
        </p>
      </div>

      {p.status !== "ready" && (
        <p className="text-[12px] text-muted">
          Search: {p.search.termination}, {p.search.candidates_evaluated} candidates evaluated.{" "}
          {p.search.feasibility_proven_impossible
            ? "A necessary condition fails (e.g. no qualified technician), so no plan exists for this event."
            : "No plan was found by this bounded search; that is not a proof that none exists."}
        </p>
      )}

      {p.changes.length > 0 && (
        <div>
          <h3 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-muted">Changes ({p.changes.length})</h3>
          <ul className="divide-y divide-line rounded-md border border-line">
            {p.changes.map((c) => {
              const K = KIND[c.kind];
              return (
                <li key={c.job_id} className="p-2 text-[12px]" data-testid={`change-${c.job_id}`}>
                  <button className="flex w-full items-center gap-1.5 text-left" onClick={() => onSelectJob(c.job_id)}>
                    <K.icon className="size-3.5 shrink-0 text-proposed" aria-hidden />
                    <span className="font-medium">{K.text}</span>
                    <span className="tabular font-semibold">{c.job_id}</span>
                    {c.forced && <Badge tone="amber">forced</Badge>}
                  </button>
                  <div className="mt-0.5 flex items-center gap-1.5 pl-5">
                    <Place p={c.before} idx={committed} /> <ArrowRight className="size-3 text-muted" aria-label="to" />
                    <Place p={c.after} idx={proposedIdx ? { ...committed, techs: new Map(proposedIdx.technicians.map((t) => [t.id, t])) } : committed} />
                  </div>
                  <p className="mt-0.5 pl-5 text-muted">{c.explanation}</p>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {p.comparison.length > 0 && <Comparison rows={p.comparison} selected={p} strategy={strategy} />}

      <details className="rounded-md border border-line text-[12px]">
        <summary className="cursor-pointer px-2 py-1.5 font-medium">
          Candidates evaluated: {validCands.length} valid, {rejected.length} rejected
        </summary>
        <div className="max-h-56 overflow-auto px-2 pb-2">
          <table className="w-full text-left text-[11.5px]">
            <thead className="text-muted"><tr><th className="py-1">Worker</th><th>Slot</th><th>Start</th><th>Changed</th><th>Shift</th></tr></thead>
            <tbody className="tabular">
              {validCands.map((c) => (
                <tr key={c.id} className={c.id === p.selected_candidate_id ? "font-semibold text-committed" : ""}>
                  <td className="py-0.5">{committed.techs.get(c.technician_id)?.name ?? c.technician_id}
                    <span className="font-normal text-muted"> · {committed.techs.get(c.technician_id) ? WORKER[workerType(committed.techs.get(c.technician_id)!)].label : ""}</span>
                    {c.id === p.selected_candidate_id && " ✓"}</td>
                  <td>{c.insertion_position}</td>
                  <td>{c.emergency_start_min !== null ? hhmm(c.emergency_start_min) : "—"}</td>
                  <td>{c.ranking!.changed_existing_jobs}</td>
                  <td>{c.ranking!.absolute_start_shift_min}m</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rejected.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-muted">
              {rejected.slice(0, 12).map((c) => (
                <li key={c.id}>
                  {committed.techs.get(c.technician_id)?.name ?? c.technician_id}
                  {c.insertion_position >= 0 && ` (slot ${c.insertion_position})`}: {c.reasons.join("; ")}
                </li>
              ))}
              {rejected.length > 12 && <li>…and {rejected.length - 12} more</li>}
            </ul>
          )}
        </div>
      </details>

      <div className="text-[12px]">
        {p.validation.valid ? (
          <p className="flex items-center gap-1 text-ok"><CheckCircle2 className="size-3.5" /> Proposed schedule passed independent validation.</p>
        ) : p.validation.violations.length ? (
          <ul className="text-emergency">{p.validation.violations.map((v, i) => <li key={i}>{v.message}</li>)}</ul>
        ) : null}
        <p className="tabular mt-1 text-muted">
          Computed in {p.runtime_ms} ms · expires {new Date(p.expires_at_utc).toLocaleTimeString()}
        </p>
      </div>

      <div className="sticky bottom-0 -mx-4 flex gap-2 border-t border-line bg-panel px-4 py-3">
        <Button variant="approve" className="flex-1" disabled={!canApprove} onClick={onApprove}
          aria-describedby={!canApprove ? "approve-why" : undefined} data-testid="approve">
          {busy === "committing" ? <Loader2 className="animate-spin" /> : <CheckCircle2 />} Approve
        </Button>
        <Button className="flex-1" onClick={onReject} disabled={busy !== null} data-testid="reject">
          {busy === "rejecting" ? <Loader2 className="animate-spin" /> : <XCircle />} {ready && !stale ? "Reject" : "Dismiss"}
        </Button>
      </div>
      {!canApprove && (
        <p id="approve-why" className="-mt-1 text-[11px] text-muted">
          {stale ? "Outdated proposals cannot be approved." : !ready ? "Only a ready, validated proposal can be approved." : "Waiting for the current request."}
        </p>
      )}
    </section>
  );
}

function Comparison({ rows, selected, strategy }: { rows: ComparisonEntry[]; selected: Proposal; strategy: Strategy | null }) {
  const chosen = selected.proposed_snapshot ? strategy : null;
  return (
    <div>
      <h3 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-muted">Strategies on the same event</h3>
      <table className="w-full text-left text-[11.5px]" data-testid="comparison">
        <thead className="text-muted">
          <tr className="[&>th]:px-1 [&>th]:py-1 [&>th]:font-medium"><th className="!pl-0">Strategy</th><th className="text-right">Jobs changed</th><th className="text-right">Shift</th><th className="text-right">Response</th><th className="text-right">Travel</th><th className="text-right">ms</th></tr>
        </thead>
        <tbody className="tabular">
          {rows.map((r) => {
            const e = r.metrics?.emergencies[0];
            return (
              <tr key={r.strategy} className={cn("[&>td]:px-1 [&>td]:py-0.5 [&>td:not(:first-child)]:text-right", r.strategy === chosen && "font-semibold")}>
                <td className="!pl-0">{strategyName(r.strategy)}{r.strategy === chosen && " (proposed)"}</td>
                {r.status === "ready" && r.metrics && r.diff_metrics ? (
                  <>
                    <td>{r.diff_metrics.changed_existing_jobs}</td>
                    <td>{r.diff_metrics.absolute_start_shift_min}m</td>
                    <td>{e?.response_min != null ? `${e.response_min}m` : "—"}</td>
                    <td>{r.metrics.travel_min}m</td>
                  </>
                ) : (
                  <td colSpan={4} className="text-muted">{r.status === "no_feasible_plan" ? "no feasible plan" : "failed"}</td>
                )}
                <td>{r.runtime_ms}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-muted">Both strategies ran on an identical copy of the committed schedule plus this event. Travel is future travel from now.</p>
    </div>
  );
}
