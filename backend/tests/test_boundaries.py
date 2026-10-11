"""Release, cancellation and exact-now boundaries that must not bypass validation."""

from backend.adapters import refresh_derived
from backend.metrics import diff_metrics, schedule_metrics
from backend.optimizer import optimize
from backend.scenario import demo_emergency, make_scenario
from backend.schemas import Location
from backend.validator import validate_schedule


def test_emergency_cannot_use_travel_from_before_its_release_at_now():
    original = make_scenario()
    proposed = optimize(original, demo_emergency()).snapshot
    emergency = next(a for a in proposed.schedule.assignments if a.job_id == "E01")
    emergency.start_min = 690
    emergency.end_min = 735
    emergency.frozen = True
    refresh_derived(proposed)
    assert "TRAVEL_INFEASIBLE" in {v.code for v in validate_schedule(proposed, original).violations}


def test_event_emergency_cannot_disappear_as_cancelled():
    original = make_scenario()
    proposed = optimize(original, demo_emergency()).snapshot
    job = next(j for j in proposed.jobs if j.id == "E01")
    job.status = "cancelled"
    proposed.schedule.assignments = [a for a in proposed.schedule.assignments if a.job_id != "E01"]
    for tech in proposed.technicians:
        route = sorted((a for a in proposed.schedule.assignments if a.technician_id == tech.id), key=lambda a: a.sequence)
        for i, a in enumerate(route):
            a.sequence = i
    refresh_derived(proposed)
    assert "EVENT_JOB_MUTATION" in {v.code for v in validate_schedule(proposed, original).violations}


def test_existing_future_work_cannot_silently_cancel():
    original = make_scenario()
    proposed = original.model_copy(deep=True)
    job = proposed.jobs[-1]
    job.status = "cancelled"
    proposed.schedule.assignments = [a for a in proposed.schedule.assignments if a.job_id != job.id]
    refresh_derived(proposed)
    assert "JOB_MUTATION" in {v.code for v in validate_schedule(proposed, original).violations}


def test_finite_extreme_coordinates_return_no_plan_instead_of_overflow():
    original = make_scenario()
    event = demo_emergency()
    event.job.location = Location(x_km=1e308, y_km=1e308)
    result = optimize(original, event)
    assert result.snapshot is None and not result.validation.valid


def test_optimize_recovers_explicit_backlog_and_accounts_for_existing_job_change():
    original = make_scenario()
    original.schedule.assignments = [a for a in original.schedule.assignments if a.job_id != "J03"]
    original.schedule.unassigned_job_ids.append("J03")
    refresh_derived(original)
    original.validation = validate_schedule(original)
    original.metrics = schedule_metrics(original)
    assert original.validation.valid and original.metrics.unassigned_jobs == 1
    result = optimize(original, None)
    assert result.snapshot is not None and not result.snapshot.schedule.unassigned_job_ids
    diff = diff_metrics(original, result.snapshot)
    assert diff.changed_existing_jobs == 1 and diff.new_jobs == 0
