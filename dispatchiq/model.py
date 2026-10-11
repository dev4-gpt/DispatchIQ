"""Core data model. Times are minutes after midnight; locations are km on a city grid."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

MIN_PER_KM = 2.0  # ~30 km/h average urban driving, Manhattan distance


def travel(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * MIN_PER_KM


@dataclass
class Tech:
    id: str
    name: str
    skills: list[str]
    home: tuple[float, float]
    shift_start: int = 8 * 60
    shift_end: int = 17 * 60
    max_overtime: int = 90


@dataclass
class Job:
    id: str
    loc: tuple[float, float]
    skill: str
    duration: int
    earliest: int  # earliest start
    latest: int    # promised latest start; starting later counts as late
    priority: int  # 1 routine, 2 important, 3 urgent, 5 emergency
    emergency: bool = False
    release: int = 0  # minute the job becomes known (emergencies arrive at the disruption)


@dataclass
class Disruption:
    time: int
    sick: list[str]            # tech ids unavailable from `time` (in-progress job is finished)
    emergencies: list[Job]     # jobs released at `time`


@dataclass
class Day:
    seed: int
    techs: list[Tech]
    jobs: list[Job]            # jobs known in the morning
    disruption: Disruption

    def tech(self, tid: str) -> Tech:
        return next(t for t in self.techs if t.id == tid)

    def all_jobs(self) -> dict[str, Job]:
        return {j.id: j for j in self.jobs + self.disruption.emergencies}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Plan = dict[str, list[str]]  # tech id -> ordered job ids


@dataclass
class Stop:
    job: str
    arrive: float
    start: float
    end: float
    travel: float
    late: float


@dataclass
class RouteResult:
    stops: list[Stop] = field(default_factory=list)
    travel: float = 0.0
    weighted_late: float = 0.0
    late_jobs: int = 0
    end: float = 0.0
    overtime: float = 0.0


def route_eval(start_time: float, start_loc: tuple[float, float], shift_end: int, seq: list[str],
               jobs: dict[str, Job]) -> RouteResult:
    """Drive a tech through `seq` from (start_time, start_loc). Waits for each job's earliest start."""
    r = RouteResult()
    t, loc = start_time, start_loc
    for jid in seq:
        j = jobs[jid]
        d = travel(loc, j.loc)
        arrive = t + d
        start = max(arrive, j.earliest, j.release)
        late = max(0.0, start - j.latest)
        end = start + j.duration
        r.stops.append(Stop(jid, arrive, start, end, d, late))
        r.travel += d
        r.weighted_late += late * j.priority
        r.late_jobs += late > 0
        t, loc = end, j.loc
    r.end = t
    r.overtime = max(0.0, t - shift_end)
    return r
