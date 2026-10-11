"""Contract-v1 operational types. Numeric coercion and unknown fields are forbidden."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^\S+$")]
Skill = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]
Minute = Annotated[int, Field(ge=0, le=1440)]
Count = Annotated[int, Field(ge=0)]
PositiveMinutes = Annotated[int, Field(gt=0, le=1440)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Strategy = Literal["stable_insertion", "first_feasible"]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", validate_assignment=True)


class Location(Model):
    x_km: Annotated[Finite, Field(ge=0)]
    y_km: Annotated[Finite, Field(ge=0)]
    latitude: Annotated[Finite, Field(ge=-90, le=90)] | None = None
    longitude: Annotated[Finite, Field(ge=-180, le=180)] | None = None

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be present or both null")
        return self


class Customer(Model):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=160)]
    site_name: Annotated[str, Field(min_length=1, max_length=160)]


class Technician(Model):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=120)]
    skills: Annotated[list[Skill], Field(min_length=1)]
    location: Location
    shift_start_min: Minute
    shift_end_min: Minute
    max_overtime_min: Minute = 0
    max_service_min: PositiveMinutes
    availability: Literal["available", "unavailable"] = "available"
    assigned_job_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def technician_rules(self):
        if len(set(self.skills)) != len(self.skills):
            raise ValueError("skills must be unique")
        if self.shift_start_min >= self.shift_end_min:
            raise ValueError("shift end must follow shift start")
        if self.shift_end_min + self.max_overtime_min > 1440:
            raise ValueError("shift and overtime must fit the scenario day")
        return self


class JobInput(Model):
    id: Identifier
    customer: Customer
    location: Location
    required_skills: Annotated[list[Skill], Field(min_length=1)]
    priority: Literal[1, 2, 3, 5]
    duration_min: PositiveMinutes
    earliest_start_min: Minute
    latest_start_min: Minute
    window_end_min: Minute
    soft_promised_start_min: Minute | None = None
    deadline_start_min: Minute | None = None
    release_min: Minute = 0
    emergency: bool = False
    locked: bool = False

    @field_validator("priority", mode="before")
    @classmethod
    def integer_priority(cls, value):
        if type(value) is not int:
            raise ValueError("priority must be an integer")
        return value

    @model_validator(mode="after")
    def job_rules(self):
        if len(set(self.required_skills)) != len(self.required_skills):
            raise ValueError("required skills must be unique")
        if not self.earliest_start_min <= self.latest_start_min <= self.window_end_min:
            raise ValueError("job window must be ordered")
        if self.emergency and (self.priority != 5 or self.deadline_start_min is None):
            raise ValueError("emergencies require priority 5 and a start deadline")
        return self


class Job(JobInput):
    status: Literal["scheduled", "completed", "in_progress", "unassigned", "cancelled"]


class Assignment(Model):
    job_id: Identifier
    technician_id: Identifier
    sequence: Count
    start_min: Minute
    end_min: Minute
    travel_min: Count
    frozen: bool


class Schedule(Model):
    assignments: list[Assignment] = Field(default_factory=list)
    unassigned_job_ids: list[Identifier] = Field(default_factory=list)


class Violation(Model):
    code: str
    message: str
    job_id: str | None = None
    technician_id: str | None = None


class Validation(Model):
    valid: bool
    violations: list[Violation] = Field(default_factory=list)


class EmergencyMetric(Model):
    job_id: Identifier
    response_min: Count | None
    deadline_met: bool


class Metrics(Model):
    scope: Literal["future_from_now"] = "future_from_now"
    travel_min: Count = 0
    unassigned_jobs: Count = 0
    soft_sla_violations: Count = 0
    soft_sla_lateness_min: Count = 0
    hard_constraint_violations: Count = 0
    overtime_min: Count = 0
    emergencies: list[EmergencyMetric] = Field(default_factory=list)


class DiffMetrics(Model):
    forced_reassignments: Count = 0
    voluntary_reassignments: Count = 0
    changed_existing_jobs: Count = 0
    start_changed_jobs: Count = 0
    absolute_start_shift_min: Count = 0
    new_jobs: Count = 0
    newly_unassigned_jobs: Count = 0


class TravelModel(Model):
    type: Literal["manhattan_grid"] = "manhattan_grid"
    min_per_km: Literal[2] = 2
    rounding: Literal["ceil"] = "ceil"
    synthetic: Literal[True] = True


class EmergencyEvent(Model):
    type: Literal["emergency"] = "emergency"
    at_min: Minute
    job: JobInput

    @model_validator(mode="after")
    def emergency_rules(self):
        if not self.job.emergency or self.job.locked or self.job.release_min != self.at_min:
            raise ValueError("event job must be an unlocked emergency released at event time")
        return self


class UnavailableEvent(Model):
    type: Literal["technician_unavailable"] = "technician_unavailable"
    at_min: Minute
    technician_id: Identifier


Event = Annotated[EmergencyEvent | UnavailableEvent, Field(discriminator="type")]


class Snapshot(Model):
    schema_version: Literal["1"] = "1"
    scenario_id: Identifier
    scenario_epoch: Identifier
    revision: Count
    date: str = "2026-10-11"
    timezone: Literal["America/New_York"] = "America/New_York"
    now_min: Minute
    travel_model: TravelModel = Field(default_factory=TravelModel)
    technicians: list[Technician]
    jobs: list[Job]
    schedule: Schedule
    validation: Validation = Field(default_factory=lambda: Validation(valid=False))
    metrics: Metrics = Field(default_factory=Metrics)
    events: list[Event] = Field(default_factory=list)

    @field_validator("scenario_epoch")
    @classmethod
    def valid_epoch(cls, value):
        UUID(value)
        return value

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value


class BaseRequest(Model):
    scenario_id: Identifier
    scenario_epoch: Identifier
    base_revision: Count

    @field_validator("scenario_epoch")
    @classmethod
    def valid_epoch(cls, value):
        UUID(value)
        return value


class PreviewRequest(BaseRequest):
    event: Event
    strategy: Strategy = "stable_insertion"


class OptimizeRequest(BaseRequest):
    strategy: Strategy = "stable_insertion"


class ProposalRequest(BaseRequest):
    proposal_id: Identifier


class Position(Model):
    technician_id: Identifier
    start_min: Minute
    end_min: Minute


class Change(Model):
    job_id: Identifier
    before: Position | None
    after: Position | None
    kind: Literal["added", "reassigned", "shifted", "unassigned"]
    forced: bool
    reason_code: str
    explanation: str
    evidence_candidate_id: str | None = None


class Ranking(Model):
    unassigned_existing: Count
    voluntary_reassignments: Count
    changed_existing_jobs: Count
    absolute_start_shift_min: Count
    emergency_response_min: Count
    added_travel_min: int
    overtime_min: Count

    def key(self) -> tuple:
        return tuple(getattr(self, name) for name in type(self).model_fields)


class Candidate(Model):
    id: Identifier
    technician_id: Identifier
    insertion_position: Count
    eligible: bool
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    ranking: Ranking | None = None
    emergency_start_min: Minute | None = None


class Comparison(Model):
    strategy: Strategy
    status: Literal["ready", "no_feasible_plan"]
    metrics: Metrics | None
    diff_metrics: DiffMetrics | None
    runtime_ms: Annotated[Finite, Field(ge=0)]
    validation: Validation


class Search(Model):
    termination: Literal["completed", "budget_exhausted", "error"]
    candidates_evaluated: Count
    feasibility_proven_impossible: bool = False


class Proposal(Model):
    proposal_id: Identifier
    scenario_id: Identifier
    scenario_epoch: Identifier
    base_revision: Count
    status: Literal["ready", "no_feasible_plan", "failed"]
    event: Event | None
    proposed_snapshot: Snapshot | None
    changes: list[Change]
    validation: Validation
    candidates: list[Candidate]
    selected_candidate_id: str | None
    comparison: list[Comparison]
    runtime_ms: Annotated[Finite, Field(ge=0)]
    search: Search
    expires_at_utc: str
    explanation: str


class HealthResponse(Model):
    status: Literal["ok"] = "ok"
    schema_version: Literal["1"] = "1"
    optimizer: Literal["feasible_insertion"] = "feasible_insertion"
    state_ready: Literal[True] = True


class CollectionMetadata(Model):
    schema_version: Literal["1"]
    scenario_id: Identifier
    scenario_epoch: Identifier
    revision: Count


class TechniciansResponse(CollectionMetadata):
    technicians: list[Technician]


class JobsResponse(CollectionMetadata):
    jobs: list[Job]


class ScheduleResponse(CollectionMetadata):
    schedule: Schedule
    validation: Validation


class MetricsResponse(CollectionMetadata):
    metrics: Metrics


class RejectResponse(Model):
    proposal_id: Identifier
    status: Literal["rejected"]
    revision: Count


class ParseRequest(BaseRequest):
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class ParseIssue(Model):
    field: str
    message: str


class ParseResponse(Model):
    scenario_id: Identifier
    scenario_epoch: Identifier
    base_revision: Count
    status: Literal["ready", "needs_input"]
    event: Event | None
    missing_fields: list[str]
    issues: list[ParseIssue]
    question: str | None
