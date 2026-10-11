"""Seeded generator of realistic field-service days with a mid-day disruption.

A day: 8-12 technicians with overlapping skills, 30-50 booked jobs with 2-4 hour
arrival windows, then at ~11:00-14:00 one or two techs call out sick and 1-3
emergency jobs (no heat, burst pipe, no power) arrive with 2-hour promises.

Seed splits (fixed, so nobody can tune on held-out days):
    dev        0-29     used by agents during search
    validation 100-129  used to pick the champion
    held-out   1000-1049 touched once at the end; hash published before search
"""

from __future__ import annotations

import hashlib
import json
import random

from .model import Day, Disruption, Job, Tech

SKILLS = ["hvac", "plumbing", "electrical"]
NAMES = ["John", "Sarah", "Mike", "Priya", "Luis", "Ava", "Omar", "Mei", "Dan", "Zoe", "Raj", "Kim"]
SPLITS = {"dev": range(0, 30), "validation": range(100, 130), "heldout": range(1000, 1050)}
CITY_KM = 30.0


def make_day(seed: int) -> Day:
    rng = random.Random(seed)
    n_techs = rng.randint(8, 12)
    techs = []
    for i in range(n_techs):
        primary = SKILLS[i % 3]
        skills = [primary] + ([rng.choice([s for s in SKILLS if s != primary])] if rng.random() < 0.45 else [])
        techs.append(Tech(id=f"T{i}", name=NAMES[i], skills=skills,
                          home=(rng.uniform(0, CITY_KM), rng.uniform(0, CITY_KM))))

    jobs = []
    n_jobs = rng.randint(30, 50)
    for k in range(n_jobs):
        start_window = rng.choice([8, 8, 10, 10, 12, 13, 14]) * 60
        width = rng.choice([120, 180, 240])
        jobs.append(Job(
            id=f"J{k}", loc=(rng.uniform(0, CITY_KM), rng.uniform(0, CITY_KM)),
            skill=rng.choices(SKILLS, weights=[5, 3, 2])[0], duration=rng.choice([45, 60, 60, 90, 120]),
            earliest=start_window, latest=start_window + width - 30,
            priority=rng.choices([1, 2, 3], weights=[6, 3, 1])[0]))

    t = rng.randint(11 * 60, 14 * 60)
    sick = rng.sample([x.id for x in techs], k=1 if rng.random() < 0.7 else 2)
    emergencies = []
    for e in range(rng.randint(1, 3)):
        emergencies.append(Job(
            id=f"E{e}", loc=(rng.uniform(0, CITY_KM), rng.uniform(0, CITY_KM)),
            skill=rng.choices(SKILLS, weights=[5, 3, 2])[0], duration=rng.choice([60, 90, 120]),
            earliest=t, latest=t + 120, priority=5, emergency=True, release=t))
    return Day(seed=seed, techs=techs, jobs=jobs, disruption=Disruption(time=t, sick=sick, emergencies=emergencies))


def split(name: str) -> list[int]:
    return list(SPLITS[name])


def heldout_hash() -> str:
    """Hash of every held-out day. Publish it (commit) before any search so tuning on it is detectable."""
    payload = json.dumps([make_day(s).to_dict() for s in split("heldout")], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
