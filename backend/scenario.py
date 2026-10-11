"""Published operational demo fixture; never touches the original held-out generator."""

from uuid import uuid4

from .adapters import refresh_derived, travel_minutes
from .metrics import schedule_metrics
from .schemas import Assignment, Customer, EmergencyEvent, Job, JobInput, Location, Schedule, Snapshot, Technician
from .validator import validate_schedule

ROSTER = [
    ("John", ["hvac"], (1, 1)),
    ("Sarah", ["plumbing"], (8, 4)),
    ("Mike", ["hvac", "electrical"], (12, 8)),
    ("Priya", ["hvac", "plumbing"], (9, 10)),
    ("Luis", ["electrical"], (15, 5)),
    ("Ava", ["hvac"], (16, 12)),
    ("Omar", ["plumbing"], (2, 15)),
    ("Mei", ["hvac", "plumbing", "electrical"], (3, 1)),
    ("Dan", ["electrical"], (18, 3)),
    ("Zoe", ["plumbing"], (7, 17)),
]


def make_scenario(*, revision: int = 0, epoch: str | None = None) -> Snapshot:
    techs, jobs, assignments = [], [], []
    for i, (name, skills, home) in enumerate(ROSTER):
        tech = Technician(id=f"T{i:02}", name=name, skills=skills, location=Location(x_km=home[0], y_km=home[1]),
                          shift_start_min=480, shift_end_min=1020, max_service_min=420)
        techs.append(tech)
        starts = [500, 690 if i == 3 else 670, 750] if i < 5 else [520, 705]
        previous_location = tech.location
        for k, start in enumerate(starts):
            loc = tech.location if k < 2 and i < 5 else Location(x_km=home[0] + 2 * k, y_km=home[1])
            duration = 45 if k == 0 else 40 if i < 5 and k == 1 else 60
            jid = f"J{len(jobs) + 1:02}"
            job = Job(id=jid, customer=Customer(id=f"C{len(jobs) + 1:02}", name=f"Customer {len(jobs) + 1}",
                                               site_name=["Residence", "Workshop", "Community center"][k]),
                      location=loc, required_skills=skills[:2] if i == 7 else [skills[0]],
                      priority=2 if k == 2 else 1, duration_min=duration,
                      earliest_start_min=start, latest_start_min=start + (90 if k else 30),
                      window_end_min=min(1020, start + duration + 120),
                      soft_promised_start_min=start, locked=i == 4 and k == 2, status="scheduled")
            jobs.append(job)
            assignments.append(Assignment(job_id=jid, technician_id=tech.id, sequence=k, start_min=start,
                                          end_min=start + duration, travel_min=travel_minutes(previous_location, loc),
                                          frozen=start <= 690))
            previous_location = loc
    snapshot = Snapshot(scenario_id="demo-v1", scenario_epoch=epoch or str(uuid4()), revision=revision,
                        now_min=690, technicians=techs, jobs=jobs, schedule=Schedule(assignments=assignments))
    refresh_derived(snapshot)
    snapshot.validation = validate_schedule(snapshot)
    if not snapshot.validation.valid:
        raise ValueError(f"Invalid published baseline: {snapshot.validation.model_dump()}")
    snapshot.metrics = schedule_metrics(snapshot)
    return snapshot


def demo_emergency(*, impossible: bool = False, job_id: str = "E01") -> EmergencyEvent:
    return EmergencyEvent(at_min=690, job=JobInput(
        id=job_id, customer=Customer(id="C99", name="Civic Clinic", site_name="Plant room"),
        location=Location(x_km=4, y_km=2), required_skills=["hvac"], priority=5, duration_min=45,
        earliest_start_min=690, latest_start_min=730, window_end_min=840,
        deadline_start_min=691 if impossible else 730, release_min=690, emergency=True))
