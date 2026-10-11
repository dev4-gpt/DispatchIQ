"""Natural-language event intake: free text -> a validated EmergencyEvent or UnavailableEvent.

The LLM only extracts what the dispatcher wrote into a small draft. The server fixes every field the
contract already determines (event time, release, priority, emergency flag, new job ID), decides
which fields are missing, and validates the result with the existing Pydantic models and against the
current snapshot. Parsing never calls the optimizer and never changes committed state.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from pydantic import ValidationError

from dispatchiq.proposers import Provider, complete_text, providers_from_env

from .schemas import EmergencyEvent, ParseIssue, ParseResponse, Snapshot, UnavailableEvent

# Same derived service window the dispatcher form uses: deadline + duration + 120 minutes.
WINDOW_SLACK_MIN = 120
MAX_TEXT_CHARS = 2000

Complete = Callable[[list[dict]], str]

PROMPT = """You turn a field-service dispatcher's message into a draft event. Extract ONLY what the
message states. Use null for anything not stated; never guess coordinates, skills, durations or deadlines.

Two event types exist:
- "emergency": a new urgent job.
- "technician_unavailable": a technician is out (sick, vehicle broke down, ...) from now on.

Current simulated time is minute {now_min} after local midnight ({clock}).
Known skills: {skills}.
Technicians (id: name, skills, availability):
{techs}
Locations are on a synthetic city grid in km (x_km east, y_km north, both >= 0).

Reply with ONLY one JSON object:
{{"type": "emergency" | "technician_unavailable" | null,
  "technician_id": string or null,        // technician_unavailable only; use an id from the list
  "customer_name": string or null,        // emergency only
  "site_name": string or null,            // emergency only, e.g. "Plant room"
  "x_km": number or null, "y_km": number or null,
  "required_skills": [string] or null,    // from the known skills
  "duration_min": integer or null,        // expected service minutes
  "respond_within_min": integer or null,  // the technician must START within this many minutes from now
  "question": string or null}}             // one short question if something needed is missing"""

EMERGENCY_FIELDS = ["customer_name", "site_name", "x_km", "y_km", "required_skills", "duration_min",
                    "respond_within_min"]


class IntakeUnavailable(Exception):
    """No LLM provider is configured."""


class IntakeFailed(Exception):
    """The LLM call failed or returned something that is not a draft."""


def llm_complete(providers: list[Provider] | None = None, timeout: float = 30.0) -> Complete:
    providers = providers if providers is not None else providers_from_env()
    if not providers:
        raise IntakeUnavailable()

    def complete(messages: list[dict]) -> str:
        from openai import OpenAI

        last = None
        for p in providers:
            try:
                client = OpenAI(base_url=p.base_url, api_key=p.api_key, timeout=timeout)
                return complete_text(client, model=p.model, messages=messages, temperature=0)[0]
            except Exception as e:  # outage or rate limit: try the next provider
                last = e
        raise IntakeFailed(f"all providers failed: {type(last).__name__}")

    return complete


def _draft(text: str) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise IntakeFailed("model output contained no JSON object")
    try:
        draft = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise IntakeFailed("model output was not valid JSON") from e
    if not isinstance(draft, dict):
        raise IntakeFailed("model output was not a JSON object")
    return draft


def _next_emergency_id(snapshot: Snapshot) -> str:
    ids = {j.id for j in snapshot.jobs}
    n = 1
    while f"E{n:02}" in ids:
        n += 1
    return f"E{n:02}"


def _as_int(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _as_float(value):
    return float(value) if isinstance(value, int) and not isinstance(value, bool) else value


def _issues_from(error: ValidationError, prefix: str) -> list[ParseIssue]:
    return [ParseIssue(field=prefix + ".".join(map(str, e["loc"])), message=e["msg"]) for e in error.errors()]


def parse_event(text: str, snapshot: Snapshot, complete: Complete) -> ParseResponse:
    now = snapshot.now_min
    skills = sorted({s for t in snapshot.technicians for s in t.skills})
    techs = "\n".join(f"- {t.id}: {t.name}, {', '.join(t.skills)}, {t.availability}" for t in snapshot.technicians)
    messages = [{"role": "system", "content": PROMPT.format(now_min=now, clock=f"{now // 60:02}:{now % 60:02}",
                                                            skills=", ".join(skills), techs=techs)},
                {"role": "user", "content": text}]
    draft = _draft(complete(messages))
    meta = dict(scenario_id=snapshot.scenario_id, scenario_epoch=snapshot.scenario_epoch, base_revision=snapshot.revision)
    question = draft.get("question") if isinstance(draft.get("question"), str) and draft["question"].strip() else None

    def needs(missing: list[str], issues: list[ParseIssue], fallback: str) -> ParseResponse:
        return ParseResponse(**meta, status="needs_input", event=None, missing_fields=missing, issues=issues,
                             question=(question or fallback)[:300])

    kind = draft.get("type")
    if kind == "technician_unavailable":
        tid = draft.get("technician_id")
        if not isinstance(tid, str) or not tid:
            return needs(["technician_id"], [], "Which technician is unavailable?")
        try:
            event = UnavailableEvent.model_validate_json(json.dumps({"type": kind, "at_min": now, "technician_id": tid}))
        except ValidationError as e:
            return needs([], _issues_from(e, ""), "Which technician is unavailable?")
        tech = next((t for t in snapshot.technicians if t.id == tid), None)
        if tech is None:
            return needs([], [ParseIssue(field="technician_id", message=f"Unknown technician {tid!r}.")],
                         "Which technician is unavailable? Please use a name from today's roster.")
        if tech.availability == "unavailable":
            return needs([], [ParseIssue(field="technician_id", message=f"{tech.name} is already unavailable.")],
                         f"{tech.name} is already marked unavailable. Did you mean another technician?")
        return ParseResponse(**meta, status="ready", event=event, missing_fields=[], issues=[], question=None)

    if kind != "emergency":
        return needs(["type"], [], "Is this a new emergency job, or is a technician unavailable?")

    missing = [f for f in EMERGENCY_FIELDS if draft.get(f) in (None, "", [])]
    if missing:
        return needs(missing, [], f"Please provide: {', '.join(missing)}.")

    issues = []
    required = draft["required_skills"]
    if not isinstance(required, list) or not all(isinstance(s, str) for s in required):
        issues.append(ParseIssue(field="required_skills", message="Must be a list of skill names."))
    else:
        required = [s.strip().lower() for s in required]
        unknown = [s for s in required if s not in skills]
        if unknown:
            issues.append(ParseIssue(field="required_skills",
                                     message=f"Unknown skill(s) {', '.join(unknown)}. Known: {', '.join(skills)}."))
    duration, within = _as_int(draft["duration_min"]), _as_int(draft["respond_within_min"])
    if not isinstance(within, int) or isinstance(within, bool) or within < 0:
        issues.append(ParseIssue(field="respond_within_min", message="Must be a non-negative whole number of minutes."))
    if not isinstance(duration, int) or isinstance(duration, bool):
        issues.append(ParseIssue(field="duration_min", message="Must be a whole number of minutes."))
    if issues:
        return needs([], issues, "Could you clarify: " + "; ".join(i.message for i in issues))

    job_id = _next_emergency_id(snapshot)
    deadline = now + within
    payload = {"type": "emergency", "at_min": now, "job": {
        "id": job_id,
        "customer": {"id": f"C-{job_id}", "name": str(draft["customer_name"]).strip(),
                     "site_name": str(draft["site_name"]).strip()},
        "location": {"x_km": _as_float(draft["x_km"]), "y_km": _as_float(draft["y_km"]),
                     "latitude": None, "longitude": None},
        "required_skills": required, "priority": 5, "duration_min": duration,
        "earliest_start_min": now, "latest_start_min": deadline,
        "window_end_min": min(1440, deadline + duration + WINDOW_SLACK_MIN),
        "soft_promised_start_min": None, "deadline_start_min": deadline, "release_min": now,
        "emergency": True, "locked": False}}
    try:
        event = EmergencyEvent.model_validate_json(json.dumps(payload))
    except ValidationError as e:
        issues = _issues_from(e, "")
        return needs([], issues, "Could you clarify: " + "; ".join(f"{i.field}: {i.message}" for i in issues))
    if event.at_min != now or event.job.id in {j.id for j in snapshot.jobs}:  # guaranteed above; checked anyway
        raise IntakeFailed("internal: event does not match the snapshot")
    return ParseResponse(**meta, status="ready", event=event, missing_fields=[], issues=[], question=None)
