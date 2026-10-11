"""Proposers write new re-plan code for each round.

- LLMProposer: any OpenAI-compatible endpoint. Put Luminal first (LLM_BASE_URL / LLM_API_KEY /
  LLM_MODEL); FALLBACK_1_* and FALLBACK_2_* are tried in order if it fails.
- RandomSearchProposer: no LLM. Mutates the numeric knobs of a parametric insertion policy.
  It is a genuine (weak) optimizer used for offline testing and as an ablation baseline
  ("is the LLM better than random search?"). It is never presented as the agent team.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent / "policies"

TASK = """You are improving a field-service dispatcher's RE-PLAN function.

Situation: it is mid-day. One or two technicians just called out sick and 1-3 emergency jobs arrived.
Write `def replan(state) -> dict` returning {tech_id: [job_id, ...]} in visiting order for the OPEN jobs.

state = {
  "time": minute of day, "min_per_km": float,
  "techs": [{"id","name","skills":[...],"sick":bool,"free_at":minute,"loc":[x,y],
             "shift_end":minute,"max_overtime":minutes,"remaining":[job ids from the morning plan]}],
  "jobs": {job_id: {"loc":[x,y],"skill":str,"duration":min,"earliest":min,"latest":min,
                    "priority":1|2|3|5,"emergency":bool,"release":min,"morning_tech":tech id or null}}
}
HARD rules (any violation = the whole day fails): sick techs get no jobs; tech must have the job's skill;
each job at most once; every emergency assigned; a tech may not finish more than max_overtime past shift_end.
COST to minimise (checker, lower is better): travel minutes + sum(lateness_minutes * priority) + overtime minutes
  + 150 * priority for each job left unscheduled + 20 per job moved from one healthy tech to another
  + minutes from each emergency's release to its start.
You may `from dispatchiq.helpers import route, route_cost, travel_min, drop_until_feasible`:
  route(state, tech, seq) -> {"travel","weighted_late","overtime","end","emergency_wait","feasible"}
  route_cost(state, tech, seq) -> float (route part of the cost; 1e6 if infeasible)
  drop_until_feasible(state, tech, seq) -> (kept_seq, dropped_ids)
Only the Python standard library is available. Must run in well under 1 second per day. Deterministic.
Return ONLY one ```python code block containing the full module."""

STRATEGIES = [
    "Make emergencies faster: choose the tech who can START the emergency soonest, not the nearest one.",
    "Add a local-search pass after insertion: try relocating and swapping open jobs within and between "
    "healthy techs, keeping a move only if total estimated cost (including the churn penalty) drops.",
    "Use regret insertion: insert first the job whose best and second-best insertion costs differ most.",
    "Re-sequence each healthy tech's remaining jobs (e.g. by time window and 2-opt) to cut lateness and travel.",
    "Reduce unscheduled high-priority jobs: allow bumping a priority-1 job to tomorrow to fit a priority-3 job.",
    "Balance load: prefer techs with slack before shift_end; avoid stacking overtime on one tech.",
]


def extract_code(text: str) -> str:
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", text, flags=re.S)
    code = max(m, key=len) if m else text
    if "def replan" not in code:
        raise ValueError("no replan() in model output")
    return code


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


def providers_from_env() -> list[Provider]:
    out = []
    for prefix in ("LLM", "FALLBACK_1", "FALLBACK_2"):
        key, url, model = (os.getenv(f"{prefix}_{k}") for k in ("API_KEY", "BASE_URL", "MODEL"))
        if key and url and model:
            out.append(Provider(prefix, url, key, model))
    return out


class LLMProposer:
    kind = "llm"

    def __init__(self, providers: list[Provider] | None = None, timeout: float = 120.0):
        self.providers = providers if providers is not None else providers_from_env()
        self.timeout = timeout
        self.tokens = 0

    def available(self) -> bool:
        return bool(self.providers)

    def propose(self, agent_idx: int, champion_code: str, feedback: str, rng: random.Random) -> tuple[str, str]:
        from openai import OpenAI

        strategy = STRATEGIES[agent_idx % len(STRATEGIES)]
        messages = [
            {"role": "system", "content": TASK},
            {"role": "user", "content": f"Current champion policy:\n```python\n{champion_code}\n```\n\n"
                                        f"Checker feedback on the champion:\n{feedback}\n\n"
                                        f"Your angle this round: {strategy}\nWrite an improved full module."},
        ]
        last = None
        for p in self.providers:
            try:
                client = OpenAI(base_url=p.base_url, api_key=p.api_key, timeout=self.timeout)
                r = client.chat.completions.create(model=p.model, messages=messages, temperature=0.7)
                if r.usage:
                    self.tokens += r.usage.total_tokens or 0
                return extract_code(r.choices[0].message.content or ""), f"{p.name}:{p.model} | {strategy}"
            except Exception as e:  # rate limit, outage, bad output: next provider
                last = e
        raise RuntimeError(f"all providers failed: {last}")


PARAM_KNOBS = {
    "emergency_by_start": [0, 1],     # pick tech who can start soonest (1) or nearest (0)
    "regret": [0, 1],                 # regret-2 ordering of orphan jobs
    "resequence": [0, 1],             # re-order each tech's remaining jobs by latest window
    "relocate_iters": [0, 1, 2, 3],   # rounds of inter-tech relocate local search
    "postpone_factor": [0.5, 0.75, 1.0, 1.25],  # postpone a job if insertion cost > factor*150*priority
}


class RandomSearchProposer:
    """No-LLM baseline: mutate knobs of policies/parametric.py around the champion."""
    kind = "random_search"

    def __init__(self):
        self.tokens = 0
        self.template = (POLICY_DIR / "parametric.py").read_text()

    def params_of(self, code: str) -> dict:
        m = re.search(r"^PARAMS = (\{.*\})$", code, flags=re.M)
        return json.loads(m.group(1)) if m else {k: v[0] for k, v in PARAM_KNOBS.items()}

    def propose(self, agent_idx: int, champion_code: str, feedback: str, rng: random.Random) -> tuple[str, str]:
        params = self.params_of(champion_code)
        for k in rng.sample(list(PARAM_KNOBS), k=rng.randint(1, 2)):
            params[k] = rng.choice(PARAM_KNOBS[k])
        code = re.sub(r"^PARAMS = .*$", "PARAMS = " + json.dumps(params), self.template, count=1, flags=re.M)
        return code, f"random_search {params}"
