// Frozen from docs/CONTRACTS.md (schema_version "1"). Do not rename fields here; report
// mismatches to the backend owner instead. All schedule times are integer minutes after
// local midnight; coordinates are synthetic grid km; IDs are opaque strings.

export type Minutes = number;

export interface Location {
  x_km: number;
  y_km: number;
  latitude: number | null;
  longitude: number | null;
}

/**
 * Contract v1.1 proposal (docs/CONTRACTS_WORKER_TYPES.md): additive, optional fields so v1
 * payloads still parse. A missing worker_type means "human"; a missing allowed_worker_types
 * means ["human"].
 */
export type WorkerType = "human" | "robot" | "agent";

export interface Technician {
  id: string;
  name: string;
  worker_type?: WorkerType;
  /** Safety/operating certifications, e.g. "robot_cowork". */
  certifications?: string[];
  skills: string[];
  location: Location;
  shift_start_min: Minutes;
  shift_end_min: Minutes;
  max_overtime_min: Minutes;
  max_service_min: Minutes;
  availability: "available" | "unavailable";
  assigned_job_ids: string[];
}

export type JobStatus = "scheduled" | "completed" | "in_progress" | "unassigned" | "cancelled";

export interface Customer {
  id: string;
  name: string;
  site_name: string;
}

export interface Job {
  id: string;
  customer: Customer;
  location: Location;
  required_skills: string[];
  priority: 1 | 2 | 3 | 5;
  duration_min: Minutes;
  earliest_start_min: Minutes;
  latest_start_min: Minutes;
  window_end_min: Minutes;
  soft_promised_start_min: Minutes | null;
  deadline_start_min: Minutes | null;
  release_min: Minutes;
  emergency: boolean;
  status: JobStatus;
  locked: boolean;
  /** Which kinds of worker may do this job. Missing = ["human"]. */
  allowed_worker_types?: WorkerType[];
  /** Physical site; work at the same site at overlapping times is checked for human-robot safety. */
  site_id?: string | null;
}

export type JobInput = Omit<Job, "status">;

export interface Assignment {
  job_id: string;
  technician_id: string;
  sequence: number;
  start_min: Minutes;
  end_min: Minutes;
  travel_min: Minutes;
  frozen: boolean;
}

export interface Schedule {
  assignments: Assignment[];
  unassigned_job_ids: string[];
}

export interface Violation {
  code: string;
  job_id?: string;
  technician_id?: string;
  message: string;
}

export interface Validation {
  valid: boolean;
  violations: Violation[];
}

export interface EmergencyMetric {
  job_id: string;
  response_min: Minutes | null;
  deadline_met: boolean;
}

export interface Metrics {
  scope: "future_from_now";
  travel_min: Minutes;
  unassigned_jobs: number;
  soft_sla_violations: number;
  soft_sla_lateness_min: Minutes;
  hard_constraint_violations: number;
  overtime_min: Minutes;
  emergencies: EmergencyMetric[];
}

export interface DiffMetrics {
  forced_reassignments: number;
  voluntary_reassignments: number;
  changed_existing_jobs: number;
  start_changed_jobs: number;
  absolute_start_shift_min: Minutes;
  new_jobs: number;
  newly_unassigned_jobs: number;
}

export interface TravelModel {
  type: "manhattan_grid";
  min_per_km: number;
  rounding: "ceil";
  synthetic: boolean;
}

export type EmergencyEvent = { type: "emergency"; at_min: Minutes; job: JobInput };
export type TechnicianUnavailableEvent = { type: "technician_unavailable"; at_min: Minutes; technician_id: string };
export type DispatchEvent = EmergencyEvent | TechnicianUnavailableEvent;

export interface Snapshot {
  schema_version: "1";
  scenario_id: string;
  scenario_epoch: string;
  revision: number;
  date: string;
  timezone: string;
  now_min: Minutes;
  travel_model: TravelModel;
  technicians: Technician[];
  jobs: Job[];
  schedule: Schedule;
  validation: Validation;
  metrics: Metrics;
  events: DispatchEvent[];
}

export interface Placement {
  technician_id: string;
  start_min: Minutes;
  end_min: Minutes;
}

export interface Change {
  job_id: string;
  before: Placement | null;
  after: Placement | null;
  kind: "added" | "reassigned" | "shifted" | "unassigned";
  forced: boolean;
  reason_code: string;
  explanation: string;
  evidence_candidate_id: string | null;
}

export interface Ranking {
  unassigned_existing: number;
  voluntary_reassignments: number;
  changed_existing_jobs: number;
  absolute_start_shift_min: Minutes;
  emergency_response_min: Minutes;
  added_travel_min: Minutes;
  overtime_min: Minutes;
}

export interface CandidateEvidence {
  id: string;
  technician_id: string;
  insertion_position: number;
  eligible: boolean;
  valid: boolean;
  reasons: string[];
  ranking: Ranking | null;
  emergency_start_min: Minutes | null;
}

export type Strategy = "stable_insertion" | "first_feasible";
export type ProposalStatus = "ready" | "no_feasible_plan" | "failed";

export interface ComparisonEntry {
  strategy: Strategy;
  status: ProposalStatus;
  metrics: Metrics | null;
  diff_metrics: DiffMetrics | null;
  runtime_ms: number;
  validation: Validation;
}

export interface SearchInfo {
  termination: "completed" | "budget_exhausted" | "error";
  candidates_evaluated: number;
  feasibility_proven_impossible: boolean;
}

export interface Proposal {
  proposal_id: string;
  scenario_id: string;
  scenario_epoch: string;
  base_revision: number;
  status: ProposalStatus;
  event: DispatchEvent | null;
  proposed_snapshot: Snapshot | null;
  changes: Change[];
  validation: Validation;
  candidates: CandidateEvidence[];
  selected_candidate_id: string | null;
  comparison: ComparisonEntry[];
  runtime_ms: number;
  search: SearchInfo;
  expires_at_utc: string;
  explanation: string;
}

export interface BaseMetadata {
  scenario_id: string;
  scenario_epoch: string;
  base_revision: number;
}

export interface Health {
  status: "ok";
  schema_version: "1";
  optimizer: string;
  state_ready: boolean;
}

export interface RejectResult {
  proposal_id: string;
  status: "rejected";
  revision: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; current_revision?: number; details?: unknown[] };
}

export function baseOf(s: Snapshot): BaseMetadata {
  return { scenario_id: s.scenario_id, scenario_epoch: s.scenario_epoch, base_revision: s.revision };
}
