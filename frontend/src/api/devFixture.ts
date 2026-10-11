/**
 * DEVELOPMENT FIXTURE — NOT THE DISPATCH API.
 *
 * A small in-browser stand-in that follows docs/CONTRACTS.md so the operations UI can be
 * built and browser-tested before Developer 1's FastAPI service exists. It computes real
 * insertion candidates, timings, validation and metrics on a synthetic day with 7 people,
 * 2 field robots and 1 AI quoting agent (25 booked jobs); nothing here is canned. It also
 * implements the v1.1 proposal in docs/CONTRACTS_WORKER_TYPES.md (worker types and the
 * human-robot co-presence safety rule). It is enabled only by `npm run dev:fixture` or
 * `?fixture=dev`, and the UI shows a persistent banner while it is active.
 *
 * It is NOT the backend's optimizer or validator and its numbers must never be presented
 * as backend results. Integration acceptance must run against the real API.
 */
import { ApiError, type Transport } from "./client";
import type {
  Assignment,
  BaseMetadata,
  CandidateEvidence,
  Change,
  ComparisonEntry,
  DiffMetrics,
  DispatchEvent,
  Job,
  JobInput,
  Metrics,
  Proposal,
  Ranking,
  Snapshot,
  Strategy,
  Technician,
  Validation,
  Violation,
  WorkerType,
} from "./types";

const NOW = 690; // 11:30
const MIN_PER_KM = 2;
const TTL_MS = 15 * 60 * 1000;

export const travel = (a: { x_km: number; y_km: number }, b: { x_km: number; y_km: number }) =>
  Math.ceil(MIN_PER_KM * (Math.abs(a.x_km - b.x_km) + Math.abs(a.y_km - b.y_km)));

const loc = (x: number, y: number) => ({ x_km: x, y_km: y, latitude: null, longitude: null });

// ---------- deterministic fixture ----------
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

type Seed = { name: string; type: WorkerType; skills: string[]; x: number; y: number; certs?: string[]; capacity?: number; jobs: number };

// 7 people, 2 field robots, 1 AI agent; 25 booked jobs.
const WORKERS: Seed[] = [
  { name: "Mike", type: "human", skills: ["hvac"], x: 2, y: 3, certs: ["robot_cowork"], jobs: 3 },
  { name: "Sarah", type: "human", skills: ["hvac", "electrical"], x: 14, y: 4, jobs: 3 },
  { name: "John", type: "human", skills: ["plumbing"], x: 6, y: 15, certs: ["robot_cowork"], jobs: 2 },
  { name: "Priya", type: "human", skills: ["electrical"], x: 18, y: 16, jobs: 3 },
  { name: "Luis", type: "human", skills: ["hvac", "plumbing"], x: 10, y: 9, certs: ["robot_cowork"], jobs: 2 },
  { name: "Ava", type: "human", skills: ["plumbing"], x: 3, y: 18, jobs: 3 },
  { name: "Omar", type: "human", skills: ["hvac"], x: 17, y: 10, jobs: 2 },
  { name: "Rover-1", type: "robot", skills: ["inspection"], x: 9, y: 2, capacity: 300, jobs: 2 },
  { name: "Atlas-2", type: "robot", skills: ["inspection"], x: 12, y: 17, capacity: 300, jobs: 2 },
  { name: "Quote Agent", type: "agent", skills: ["quoting"], x: 0, y: 0, jobs: 3 },
];
const CUSTOMERS = ["Taylor", "Nguyen", "Okafor", "Garcia", "Kim", "Patel", "Rossi", "Haddad", "Levy", "Brooks",
  "Chen", "Silva", "Novak", "Ito", "Moreau", "Khan", "Dubois", "Park", "Weber", "Costa", "Ali", "Berg", "Sato", "Ruiz", "Shah"];
const SITES = ["Residence", "Bakery", "Dental office", "Apartment 4B", "Warehouse", "Cafe", "Clinic", "Townhouse"];

const typeOf = (t: Technician): WorkerType => t.worker_type ?? "human";
const typeName = (w: WorkerType) => (w === "human" ? "person" : w === "robot" ? "robot" : "AI agent");
const aTypeName = (w: WorkerType) => (w === "agent" ? "an AI agent" : `a ${typeName(w)}`);
const fmt = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
/** Agents work remotely: no travel. Everyone else drives the synthetic grid. */
export const travelFor = (t: Technician, a: { x_km: number; y_km: number }, b: { x_km: number; y_km: number }) =>
  typeOf(t) === "agent" ? 0 : travel(a, b);

function buildFixture(): Snapshot {
  const r = rng(15);
  const technicians: Technician[] = WORKERS.map((w, i) => ({
    id: `T${String(i).padStart(2, "0")}`, name: w.name, worker_type: w.type, certifications: w.certs ?? [],
    skills: w.skills, location: loc(w.x, w.y),
    shift_start_min: 480, shift_end_min: 1020, max_overtime_min: 0, max_service_min: w.capacity ?? 420,
    availability: "available", assigned_job_ids: [],
  }));
  const jobs: Job[] = [];
  const assignments: Assignment[] = [];
  let k = 0;
  technicians.forEach((t, ti) => {
    const kind = typeOf(t);
    let at = t.location;
    // Robots start mid-morning so one of them is working on site around "now" (11:30).
    let free = t.shift_start_min + (kind === "robot" ? 150 : 0);
    for (let seq = 0; seq < WORKERS[ti].jobs; seq++) {
      const id = `J${String(++k).padStart(2, "0")}`;
      const p = loc(Math.round(r() * 20), Math.round(r() * 20));
      const dur = kind === "agent" ? [20, 30, 45][Math.floor(r() * 3)] : [45, 60, 60, 90, 75][Math.floor(r() * 5)];
      const tr = travelFor(t, at, p);
      const arrive = free + tr + Math.floor(r() * 3) * (kind === "agent" ? 60 : 15);
      const earliest = Math.floor(arrive / 30) * 30;
      const start = Math.max(arrive, earliest);
      const latest = earliest + 90 + Math.floor(r() * 3) * 30;
      jobs.push({
        id, customer: { id: `C${String(k).padStart(2, "0")}`, name: CUSTOMERS[k - 1],
          site_name: kind === "agent" ? "Quote request" : kind === "robot" ? "Drain line" : SITES[k % SITES.length] },
        location: p, required_skills: [t.skills[seq % t.skills.length]], priority: ([1, 1, 2, 3] as const)[Math.floor(r() * 4)],
        duration_min: dur, earliest_start_min: earliest, latest_start_min: latest,
        window_end_min: latest + dur + 60, soft_promised_start_min: earliest + 60, deadline_start_min: null,
        release_min: 0, emergency: false, status: "scheduled", locked: false,
        allowed_worker_types: [kind], site_id: `S${String(k).padStart(2, "0")}`,
      });
      assignments.push({ job_id: id, technician_id: t.id, sequence: seq, start_min: start, end_min: start + dur, travel_min: tr, frozen: false });
      if (kind !== "agent") at = p;
      free = start + dur;
    }
  });
  const snap: Snapshot = {
    schema_version: "1", scenario_id: "dev-fixture-v1", scenario_epoch: crypto.randomUUID(), revision: 0,
    date: "2026-10-11", timezone: "America/New_York", now_min: NOW,
    travel_model: { type: "manhattan_grid", min_per_km: MIN_PER_KM, rounding: "ceil", synthetic: true },
    technicians, jobs, schedule: { assignments, unassigned_job_ids: [] },
    validation: { valid: true, violations: [] }, metrics: emptyMetrics(), events: [],
  };
  return finalize(snap);
}

// ---------- engine ----------
function emptyMetrics(): Metrics {
  return { scope: "future_from_now", travel_min: 0, unassigned_jobs: 0, soft_sla_violations: 0, soft_sla_lateness_min: 0,
    hard_constraint_violations: 0, overtime_min: 0, emergencies: [] };
}

const clone = <T,>(x: T): T => structuredClone(x);

function deriveStatuses(s: Snapshot) {
  const byJob = new Map(s.schedule.assignments.map((a) => [a.job_id, a]));
  for (const j of s.jobs) {
    if (j.status === "cancelled") continue;
    const a = byJob.get(j.id);
    if (!a) j.status = "unassigned";
    else j.status = a.end_min <= s.now_min ? "completed" : a.start_min <= s.now_min ? "in_progress" : "scheduled";
  }
  for (const a of s.schedule.assignments) a.frozen = a.start_min <= s.now_min;
  for (const t of s.technicians)
    t.assigned_job_ids = s.schedule.assignments.filter((a) => a.technician_id === t.id).sort((a, b) => a.sequence - b.sequence).map((a) => a.job_id);
}

function finalize(s: Snapshot): Snapshot {
  deriveStatuses(s);
  s.validation = validate(s);
  s.metrics = metrics(s);
  return s;
}

export function validate(s: Snapshot, base?: Snapshot): Validation {
  const v: Violation[] = [];
  const jobs = new Map(s.jobs.map((j) => [j.id, j]));
  const techs = new Map(s.technicians.map((t) => [t.id, t]));
  const seen = new Set<string>();
  for (const a of s.schedule.assignments) {
    const j = jobs.get(a.job_id);
    const t = techs.get(a.technician_id);
    if (!j) { v.push({ code: "UNKNOWN_JOB", job_id: a.job_id, message: `Unknown job ${a.job_id}` }); continue; }
    if (!t) { v.push({ code: "UNKNOWN_TECHNICIAN", technician_id: a.technician_id, message: `Unknown technician ${a.technician_id}` }); continue; }
    if (seen.has(a.job_id)) v.push({ code: "DUPLICATE_ASSIGNMENT", job_id: a.job_id, message: `${a.job_id} assigned twice` });
    seen.add(a.job_id);
    if (!j.required_skills.every((k) => t.skills.includes(k)))
      v.push({ code: "SKILL_MISMATCH", job_id: j.id, technician_id: t.id, message: `${t.name} lacks ${j.required_skills.join(", ")}` });
    const allowed = j.allowed_worker_types ?? ["human"];
    if (!allowed.includes(typeOf(t)))
      v.push({ code: "WORKER_TYPE_NOT_ALLOWED", job_id: j.id, technician_id: t.id, message: `${j.id} allows ${allowed.map(typeName).join("/")} only; ${t.name} is ${aTypeName(typeOf(t))}` });
    if (!a.frozen && t.availability !== "available")
      v.push({ code: "TECH_UNAVAILABLE", job_id: j.id, technician_id: t.id, message: `${t.name} is unavailable` });
    if (a.end_min !== a.start_min + j.duration_min) v.push({ code: "BAD_DURATION", job_id: j.id, message: `${j.id} end ≠ start + duration` });
    if (a.start_min < j.earliest_start_min || a.start_min < j.release_min) v.push({ code: "TOO_EARLY", job_id: j.id, message: `${j.id} starts before its window` });
    if (a.start_min > j.latest_start_min) v.push({ code: "LATE_START", job_id: j.id, message: `${j.id} starts after its latest start` });
    if (a.end_min > j.window_end_min) v.push({ code: "WINDOW_END", job_id: j.id, message: `${j.id} ends after its window` });
    if (j.deadline_start_min !== null && a.start_min > j.deadline_start_min) v.push({ code: "DEADLINE_MISSED", job_id: j.id, message: `${j.id} misses its response deadline` });
    if (!a.frozen && a.start_min < s.now_min) v.push({ code: "IN_PAST", job_id: j.id, message: `${j.id} scheduled in the past` });
  }
  for (const j of s.jobs) if (j.status !== "cancelled" && !seen.has(j.id) && !s.schedule.unassigned_job_ids.includes(j.id))
    v.push({ code: "UNACCOUNTED_JOB", job_id: j.id, message: `${j.id} is neither assigned nor unassigned` });
  for (const t of s.technicians) {
    const route = s.schedule.assignments.filter((a) => a.technician_id === t.id).sort((a, b) => a.sequence - b.sequence);
    let at = t.location, free = t.shift_start_min, service = 0;
    route.forEach((a, i) => {
      const j = jobs.get(a.job_id);
      if (!j) return;
      if (a.sequence !== i) v.push({ code: "BAD_SEQUENCE", technician_id: t.id, message: `${t.name} route sequence is not contiguous` });
      const tr = travelFor(t, at, j.location);
      if (a.travel_min !== tr) v.push({ code: "BAD_TRAVEL", job_id: j.id, message: `${j.id} travel should be ${tr} min` });
      if (a.start_min < free + tr) v.push({ code: "OVERLAP_OR_TRAVEL", job_id: j.id, technician_id: t.id, message: `${t.name} cannot reach ${j.id} by ${a.start_min}` });
      at = j.location; free = a.end_min; service += j.duration_min;
    });
    if (free > t.shift_end_min + t.max_overtime_min) v.push({ code: "SHIFT_END", technician_id: t.id, message: `${t.name} works past shift end` });
    if (service > t.max_service_min) v.push({ code: "CAPACITY", technician_id: t.id, message: `${t.name} exceeds service capacity` });
  }
  // Human-robot safety: a person working at the same site at the same time as a robot must be
  // certified for robot co-work.
  for (const ra of s.schedule.assignments) {
    const rt = techs.get(ra.technician_id), rj = jobs.get(ra.job_id);
    if (!rt || !rj?.site_id || typeOf(rt) !== "robot") continue;
    for (const ha of s.schedule.assignments) {
      const ht = techs.get(ha.technician_id), hj = jobs.get(ha.job_id);
      if (!ht || !hj || typeOf(ht) !== "human" || hj.site_id !== rj.site_id) continue;
      const lo = Math.max(ha.start_min, ra.start_min), hi = Math.min(ha.end_min, ra.end_min);
      if (lo < hi && !(ht.certifications ?? []).includes("robot_cowork"))
        v.push({ code: "SAFETY_ROBOT_COPRESENCE", job_id: hj.id, technician_id: ht.id,
          message: `Safety: ${ht.name} would work beside robot ${rt.name} at ${rj.customer.name} ${fmt(lo)}–${fmt(hi)} without robot co-work certification` });
    }
  }
  if (base) for (const b of base.schedule.assignments) {
    if (!b.frozen && !base.jobs.find((j) => j.id === b.job_id)?.locked) continue;
    const a = s.schedule.assignments.find((x) => x.job_id === b.job_id);
    if (!a || a.technician_id !== b.technician_id || a.start_min !== b.start_min || a.end_min !== b.end_min)
      v.push({ code: "FROZEN_MUTATION", job_id: b.job_id, message: `${b.job_id} is frozen/locked and cannot change` });
  }
  return { valid: v.length === 0, violations: v };
}

function metrics(s: Snapshot): Metrics {
  const jobs = new Map(s.jobs.map((j) => [j.id, j]));
  const m = emptyMetrics();
  for (const a of s.schedule.assignments) {
    const j = jobs.get(a.job_id)!;
    if (a.start_min >= s.now_min) m.travel_min += a.travel_min;
    if (j.soft_promised_start_min !== null && a.start_min > j.soft_promised_start_min && a.start_min >= s.now_min) {
      m.soft_sla_violations += 1;
      m.soft_sla_lateness_min += a.start_min - j.soft_promised_start_min;
    }
  }
  for (const t of s.technicians) {
    const end = Math.max(0, ...s.schedule.assignments.filter((a) => a.technician_id === t.id).map((a) => a.end_min));
    m.overtime_min += Math.max(0, end - t.shift_end_min);
  }
  m.unassigned_jobs = s.schedule.unassigned_job_ids.length;
  m.hard_constraint_violations = s.validation.violations.length;
  for (const j of s.jobs.filter((x) => x.emergency)) {
    const a = s.schedule.assignments.find((x) => x.job_id === j.id);
    m.emergencies.push({ job_id: j.id, response_min: a ? a.start_min - j.release_min : null,
      deadline_met: !!a && (j.deadline_start_min === null || a.start_min <= j.deadline_start_min) });
  }
  return m;
}

/** Re-time one technician's route after its frozen prefix, inserting `job` at `pos`. */
function insertInto(s: Snapshot, tech: Technician, job: Job, pos: number): Assignment[] {
  const jobs = new Map(s.jobs.map((j) => [j.id, j]));
  const route = s.schedule.assignments.filter((a) => a.technician_id === tech.id).sort((a, b) => a.sequence - b.sequence);
  const frozen = route.filter((a) => a.frozen);
  const flexible = route.filter((a) => !a.frozen).map((a) => a.job_id);
  flexible.splice(pos, 0, job.id);
  const out: Assignment[] = frozen.map((a) => ({ ...a }));
  let at = frozen.length ? jobs.get(frozen[frozen.length - 1].job_id)!.location : tech.location;
  let free = frozen.length ? frozen[frozen.length - 1].end_min : tech.shift_start_min;
  for (const id of flexible) {
    const j = jobs.get(id)!;
    const tr = travelFor(tech, at, j.location);
    // A technician idle before "now" departs no earlier than now; travel always counts.
    const start = Math.max(Math.max(free, s.now_min) + tr, j.earliest_start_min, j.release_min);
    out.push({ job_id: id, technician_id: tech.id, sequence: out.length, start_min: start, end_min: start + j.duration_min, travel_min: tr, frozen: false });
    at = j.location;
    free = start + j.duration_min;
  }
  return out;
}

function diff(base: Snapshot, next: Snapshot, candidateId: string | null): { changes: Change[]; diff: DiffMetrics } {
  const before = new Map(base.schedule.assignments.map((a) => [a.job_id, a]));
  const changes: Change[] = [];
  const d: DiffMetrics = { forced_reassignments: 0, voluntary_reassignments: 0, changed_existing_jobs: 0, start_changed_jobs: 0,
    absolute_start_shift_min: 0, new_jobs: 0, newly_unassigned_jobs: 0 };
  const techName = (id: string) => next.technicians.find((t) => t.id === id)?.name ?? id;
  for (const a of next.schedule.assignments) {
    const b = before.get(a.job_id);
    const after = { technician_id: a.technician_id, start_min: a.start_min, end_min: a.end_min };
    if (!b) {
      d.new_jobs += 1;
      const j = next.jobs.find((x) => x.id === a.job_id)!;
      changes.push({ job_id: a.job_id, before: null, after, kind: "added", forced: false, reason_code: j.emergency ? "EMERGENCY_INSERTION" : "NEW_JOB",
        explanation: `${techName(a.technician_id)} is qualified (${j.required_skills.join(", ")}) and starts ${a.start_min - j.release_min} min after release` +
          (j.deadline_start_min !== null ? `, ${j.deadline_start_min - a.start_min} min before the response deadline.` : "."),
        evidence_candidate_id: candidateId });
      continue;
    }
    const moved = b.technician_id !== a.technician_id;
    const shift = a.start_min - b.start_min;
    if (!moved && shift === 0) continue;
    d.changed_existing_jobs += 1;
    if (shift !== 0) { d.start_changed_jobs += 1; d.absolute_start_shift_min += Math.abs(shift); }
    if (moved) d.voluntary_reassignments += 1;
    changes.push({ job_id: a.job_id, before: { technician_id: b.technician_id, start_min: b.start_min, end_min: b.end_min }, after,
      kind: moved ? "reassigned" : "shifted", forced: false, reason_code: "TRAVEL_AFTER_EMERGENCY",
      explanation: `Starts ${Math.abs(shift)} min ${shift > 0 ? "later" : "earlier"} to fit the new work and travel, still inside its hard window.`,
      evidence_candidate_id: candidateId });
  }
  return { changes, diff: d };
}

const RANK_ORDER: (keyof Ranking)[] = ["unassigned_existing", "voluntary_reassignments", "changed_existing_jobs",
  "absolute_start_shift_min", "emergency_response_min", "added_travel_min", "overtime_min"];
const cmpRank = (a: Ranking, b: Ranking) => {
  for (const k of RANK_ORDER) if (a[k] !== b[k]) return a[k] - b[k];
  return 0;
};

interface Evaluated { evidence: CandidateEvidence; snapshot: Snapshot | null }

function evaluateCandidates(base: Snapshot, job: Job): Evaluated[] {
  const out: Evaluated[] = [];
  const working = clone(base);
  working.jobs.push(job);
  for (const t of working.technicians) {
    const missing = job.required_skills.filter((k) => !t.skills.includes(k));
    const allowed = job.allowed_worker_types ?? ["human"];
    const typeOk = allowed.includes(typeOf(t));
    if (t.availability !== "available" || !typeOk || missing.length) {
      const reason = t.availability !== "available" ? "Unavailable"
        : !typeOk ? `Job needs ${allowed.map(typeName).join(" or ")}; this is ${aTypeName(typeOf(t))}`
        : `Missing skill: ${missing.join(", ")}`;
      out.push({ snapshot: null, evidence: { id: `CAND-${t.id}`, technician_id: t.id, insertion_position: -1, eligible: false, valid: false,
        reasons: [reason], ranking: null, emergency_start_min: null } });
      continue;
    }
    const flexibleCount = working.schedule.assignments.filter((a) => a.technician_id === t.id && !a.frozen).length;
    for (let pos = 0; pos <= flexibleCount; pos++) {
      const s = clone(working);
      s.schedule.assignments = s.schedule.assignments.filter((a) => a.technician_id !== t.id).concat(insertInto(s, t, job, pos));
      deriveStatuses(s);
      s.validation = validate(s, base);
      s.metrics = metrics(s);
      const id = `CAND-${t.id}-${pos}`;
      const ea = s.schedule.assignments.find((a) => a.job_id === job.id)!;
      if (!s.validation.valid) {
        out.push({ snapshot: null, evidence: { id, technician_id: t.id, insertion_position: pos, eligible: true, valid: false,
          reasons: [...new Set(s.validation.violations.map((x) => x.message))].slice(0, 3), ranking: null, emergency_start_min: ea.start_min } });
        continue;
      }
      const { diff: d } = diff(base, s, id);
      const ranking: Ranking = { unassigned_existing: 0, voluntary_reassignments: d.voluntary_reassignments, changed_existing_jobs: d.changed_existing_jobs,
        absolute_start_shift_min: d.absolute_start_shift_min, emergency_response_min: ea.start_min - job.release_min,
        added_travel_min: s.metrics.travel_min - base.metrics.travel_min, overtime_min: s.metrics.overtime_min };
      out.push({ snapshot: s, evidence: { id, technician_id: t.id, insertion_position: pos, eligible: true, valid: true, reasons: [], ranking, emergency_start_min: ea.start_min } });
    }
  }
  return out;
}

function pick(cands: Evaluated[], strategy: Strategy): Evaluated | undefined {
  const ok = cands.filter((c) => c.snapshot && c.evidence.ranking);
  if (strategy === "first_feasible") return ok[0];
  return [...ok].sort((a, b) => cmpRank(a.evidence.ranking!, b.evidence.ranking!))[0];
}

// ---------- store ----------
interface Stored { proposal: Proposal; state: "ready" | "rejected" | "consumed"; expires: number }
let committed = buildFixture();
const proposals = new Map<string, Stored>();
let counter = 0;

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
function checkBase(base: BaseMetadata) {
  if (base.scenario_id !== committed.scenario_id || base.scenario_epoch !== committed.scenario_epoch)
    throw new ApiError(409, "SCENARIO_CHANGED", "The scenario was reset or changed.", committed.revision);
  if (base.base_revision !== committed.revision)
    throw new ApiError(409, "STALE_PROPOSAL", "The schedule changed. Preview this event again.", committed.revision);
}

function validateEmergencyInput(job: JobInput, at: number) {
  const bad = (m: string) => { throw new ApiError(422, "INVALID_INPUT", m); };
  if (!job.id || committed.jobs.some((j) => j.id === job.id)) bad("Job ID must be new and non-empty.");
  if (!job.emergency || job.priority !== 5) bad("Emergency jobs must have emergency=true and priority 5.");
  if (job.release_min !== at || at !== committed.now_min) bad("Release and event time must equal the current time.");
  if (!job.required_skills.length) bad("At least one required skill is needed.");
  if (job.allowed_worker_types && (!job.allowed_worker_types.length ||
      job.allowed_worker_types.some((w) => !["human", "robot", "agent"].includes(w)))) bad("allowed_worker_types must list human, robot or agent.");
  if (!(job.duration_min > 0) || !Number.isInteger(job.duration_min)) bad("Duration must be a positive integer.");
}

/** Fixture-only test hook: another dispatcher commits a change, so open proposals become stale. */
export function simulateExternalCommit() {
  committed = finalize({ ...clone(committed), revision: committed.revision + 1 });
  for (const [, p] of proposals) if (p.state === "ready") p.state = "rejected";
}
if (typeof window !== "undefined") (window as unknown as Record<string, unknown>).__dispatchiqFixture = { simulateExternalCommit };

export const devFixtureTransport: Transport = {
  kind: "dev-fixture",
  async health() {
    await delay(60);
    return { status: "ok", schema_version: "1", optimizer: "dev_fixture_insertion", state_ready: true };
  },
  async scenario() {
    await delay(120);
    return clone(committed);
  },
  async preview(base, event: DispatchEvent, strategy) {
    await delay(350);
    checkBase(base);
    if (event.type !== "emergency") throw new ApiError(422, "INVALID_INPUT", "The dev fixture only supports emergency events.");
    validateEmergencyInput(event.job, event.at_min);
    const job: Job = { ...event.job, status: "scheduled" };
    const t0 = performance.now();
    const cands = evaluateCandidates(committed, job);
    const chosen = pick(cands, strategy);
    const runtime = Math.round((performance.now() - t0) * 10) / 10;
    const comparison: ComparisonEntry[] = (["stable_insertion", "first_feasible"] as Strategy[]).map((st) => {
      const t1 = performance.now();
      const c = pick(cands, st);
      return { strategy: st, status: c ? "ready" : "no_feasible_plan", metrics: c?.snapshot?.metrics ?? null,
        diff_metrics: c?.snapshot ? diff(committed, c.snapshot, c.evidence.id).diff : null,
        runtime_ms: Math.round((runtime + performance.now() - t1) * 10) / 10,
        validation: c?.snapshot?.validation ?? { valid: false, violations: [] } };
    });
    const id = `P-${++counter}`;
    const skillGap = cands.every((c) => !c.evidence.eligible);
    const proposal: Proposal = {
      proposal_id: id, ...{ scenario_id: committed.scenario_id, scenario_epoch: committed.scenario_epoch }, base_revision: committed.revision,
      status: chosen ? "ready" : "no_feasible_plan", event, proposed_snapshot: null, changes: [], validation: { valid: false, violations: [] },
      candidates: cands.map((c) => c.evidence), selected_candidate_id: chosen?.evidence.id ?? null, comparison, runtime_ms: runtime,
      search: { termination: "completed", candidates_evaluated: cands.length, feasibility_proven_impossible: !chosen && skillGap },
      expires_at_utc: new Date(Date.now() + TTL_MS).toISOString(), explanation: "",
    };
    if (chosen?.snapshot) {
      const snap = chosen.snapshot;
      snap.events = [...committed.events, event];
      proposal.proposed_snapshot = snap;
      proposal.validation = snap.validation;
      proposal.changes = diff(committed, snap, chosen.evidence.id).changes;
      const tech = snap.technicians.find((t) => t.id === chosen.evidence.technician_id)!;
      const r = chosen.evidence.ranking!;
      proposal.explanation = `Assign ${job.id} to ${tech.name} (${typeName(typeOf(tech))}): qualified, starts ${r.emergency_response_min} min after the call` +
        (job.deadline_start_min !== null ? ` (deadline ${job.deadline_start_min - job.release_min} min)` : "") +
        `. ${r.changed_existing_jobs} existing job(s) change, total start shift ${r.absolute_start_shift_min} min, ` +
        `${r.voluntary_reassignments} reassigned. Chosen by strategy "${strategy}" among ${cands.filter((c) => c.evidence.valid).length} valid candidates evaluated in this preview.`;
    } else {
      proposal.explanation = skillGap
        ? `No technician has the required skill (${job.required_skills.join(", ")}). No plan is possible without one.`
        : `No valid insertion was found among ${cands.length} candidates under this search. This is not a proof that no plan exists.`;
    }
    proposals.set(id, { proposal, state: "ready", expires: Date.now() + TTL_MS });
    return clone(proposal);
  },
  async commit(base, proposalId) {
    await delay(200);
    const p = proposals.get(proposalId);
    if (!p) throw new ApiError(404, "UNKNOWN_PROPOSAL", "Unknown proposal.");
    if (p.state === "consumed") throw new ApiError(409, "PROPOSAL_CONSUMED", "Already approved.", committed.revision);
    if (p.state === "rejected") throw new ApiError(409, "PROPOSAL_REJECTED", "Already rejected.", committed.revision);
    if (Date.now() > p.expires) throw new ApiError(410, "PROPOSAL_EXPIRED", "Proposal expired.", committed.revision);
    checkBase(base);
    if (p.proposal.base_revision !== committed.revision || p.proposal.scenario_epoch !== committed.scenario_epoch)
      throw new ApiError(409, "STALE_PROPOSAL", "The schedule changed. Preview this event again.", committed.revision);
    if (p.proposal.status !== "ready" || !p.proposal.proposed_snapshot)
      throw new ApiError(409, "STALE_PROPOSAL", "Only a ready proposal can be approved.", committed.revision);
    const next = clone(p.proposal.proposed_snapshot);
    next.revision = committed.revision + 1;
    next.validation = validate(next, committed);
    if (!next.validation.valid) throw new ApiError(409, "STALE_PROPOSAL", "Revalidation failed.", committed.revision);
    committed = finalize(next);
    p.state = "consumed";
    for (const [, other] of proposals) if (other.state === "ready") other.state = "rejected";
    return clone(committed);
  },
  async reject(base, proposalId) {
    await delay(120);
    const p = proposals.get(proposalId);
    if (!p) throw new ApiError(404, "UNKNOWN_PROPOSAL", "Unknown proposal.");
    checkBase(base);
    if (p.state !== "ready") throw new ApiError(409, p.state === "consumed" ? "PROPOSAL_CONSUMED" : "PROPOSAL_REJECTED", "Proposal is not open.");
    p.state = "rejected";
    return { proposal_id: proposalId, status: "rejected", revision: committed.revision };
  },
  async reset(base) {
    await delay(150);
    checkBase(base);
    const rev = committed.revision + 1;
    committed = buildFixture();
    committed.revision = rev;
    proposals.clear();
    return clone(committed);
  },
};
