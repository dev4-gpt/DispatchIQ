"""Critic v2: fixed approach families, so the critic refines approaches instead of collapsing them.

Critic v1 could rewrite every strategy hint; in llm-team (v1) it turned six different approaches into
variations of one idea within two rounds. v2 keeps the six original approaches as families:

- One family per agent slot. With fewer agents than families, slots rotate through the families by
  round, so a single agent works through all of them.
- Each round the critic writes exactly one refinement line per family, from that family's own results.
  It cannot delete a family. A missing refinement keeps the previous one.
- One wildcard: the weakest family, once it has been tried in at least 2 rounds, may be replaced by a
  new approach that differs from the other five. At most one family is a wildcard at any time.
- Coding fixes (crashes, mutation-while-iterating, ...) go into the shared lessons, never a hint slot.
- The critic sees the champion's mean dev-day cost breakdown, so claims about where cost remains come
  from numbers.

These rules are enforced here, in code, not only asked for in the prompt.
"""

from __future__ import annotations

import json
import re

from .proposers import MAX_HINT_CHARS, STRATEGIES, TASK, _chat

FAMILY_NAMES = ["emergency-start", "local-search", "regret-insertion", "resequence", "bump-low-priority",
                "load-balance"]
MAX_LESSONS_PER_ROUND = 5
MIN_ROUNDS_FOR_WILDCARD = 2
MAX_SIMILARITY = 0.5  # word-overlap (Jaccard) above this with another family = not a different approach

CODING_FIX = re.compile(
    r"\b(bugs?|crash\w*|exceptions?|traceback|mutat\w*|while iterating|during iteration|set changed size|"
    r"syntax|typeerror|keyerror|indexerror|valueerror|attributeerror|runtimeerror|import\w*|stdout|print\(|"
    r"fresh list|copy of the list|deepcopy|recursion|infinite loop)\b", re.I)
STOPWORDS = set("a an the and or of to in on for with by from at as is are be each every any not no only "
                "that this its it their than then when while into per job jobs tech techs technician".split())


def initial_families() -> list[dict]:
    return [{"id": f"F{i + 1}", "name": FAMILY_NAMES[i], "base": STRATEGIES[i], "refinement": "",
             "origin": "original", "since_round": 1} for i in range(len(STRATEGIES))]


def hint(family: dict) -> str:
    return family["base"] + (f" Refinement: {family['refinement']}" if family["refinement"] else "")


def assign(families: list[dict], agents: int, r: int) -> list[dict]:
    """Family for each agent slot in round r: slot i gets family (i + (r-1)*agents) mod n.
    6 agents and 6 families: fixed one-to-one. 1 agent: family (r-1) mod 6, a full rotation every 6 rounds."""
    n = len(families)
    return [families[(i + (r - 1) * agents) % n] for i in range(agents)]


def family_stats(families: list[dict], memory: list[dict]) -> dict[str, dict]:
    """Per active family: rounds tried since it took its slot, attempts, failures, best gap to champion."""
    out = {}
    for f in families:
        rows = [m for m in memory if m.get("family") == f["id"] and m["round"] >= f["since_round"]]
        gaps = [m["gap_to_champion"] for m in rows if m["gap_to_champion"] is not None]
        out[f["id"]] = {"rounds": len({m["round"] for m in rows}), "attempts": len(rows),
                        "failures": sum(m["dev_cost"] is None for m in rows),
                        "best_gap": min(gaps) if gaps else None,
                        "promoted": sum(bool(m.get("promoted")) for m in rows)}
    return out


def wildcard_eligible(families: list[dict], memory: list[dict]) -> str | None:
    """The weakest family tried in >= 2 rounds, if replacing it keeps at most one wildcard."""
    stats = family_stats(families, memory)
    tried = [f for f in families if stats[f["id"]]["rounds"] >= MIN_ROUNDS_FOR_WILDCARD]
    if not tried:
        return None

    def weakness(f):  # higher = weaker: no feasible result at all is weakest, then the worst best gap
        s = stats[f["id"]]
        return (s["best_gap"] is None, s["best_gap"] if s["best_gap"] is not None else 0.0, s["failures"])

    weakest = max(tried, key=weakness)
    has_wildcard = any(f["origin"] != "original" for f in families)
    if has_wildcard and weakest["origin"] == "original":
        return None  # replacing it would make a second wildcard
    return weakest["id"]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower()) if w not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 1.0


CRITIC_V2 = """You are the critic on a team of agents that write a field-service RE-PLAN policy.
Each agent works on one fixed APPROACH FAMILY. A deterministic checker scores every attempt on dev days
(lower cost is better; any hard-rule violation makes a day infeasible). You never write code.

The agents' task, for context:
---
{task}
---

Your job each round:
1. "refinements": exactly ONE short line for EVERY family id listed, saying how that family should
   improve next round, based on that family's own results. Stay inside the family's approach; do not turn
   it into another family's idea. Families cannot be deleted.
2. "lessons": at most {max_lessons} short, shared lessons that every agent sees. Put ALL coding fixes
   here (crashes, exceptions, mutation while iterating, ...), never in a refinement.
3. "wildcard": {wildcard_rule}

Base claims about where cost remains on the champion cost breakdown provided (numbers), not on guesses.

Reply with ONLY one JSON object, no prose:
{{"lessons": ["..."], "refinements": {{{refinement_keys}}},
  "wildcard": null or {{"replace": "<family id>", "approach": "<one sentence>", "why_different": "<one sentence>"}}}}"""


def critic_messages(families, memory, round_table, fb, breakdown, lessons, eligible) -> list[dict]:
    stats = family_stats(families, memory)
    rule = (f'family {eligible} is the weakest after at least {MIN_ROUNDS_FOR_WILDCARD} rounds; you MAY replace it '
            "with a genuinely new approach that differs from the other five families, or return null."
            if eligible else "no family is eligible for replacement this round; return null.")
    fam_lines = []
    for f in families:
        s = stats[f["id"]]
        best = "-" if s["best_gap"] is None else f"{s['best_gap']:+.1f}"
        fam_lines.append(f"- {f['id']} ({f['name']}, {f['origin']}): {f['base']}\n"
                         f"    current refinement: {f['refinement'] or '(none)'}\n"
                         f"    results: {s['rounds']} rounds, {s['attempts']} attempts, {s['failures']} failed, "
                         f"best gap to champion {best}, promoted {s['promoted']}x")
    bd = ("(not available)" if not breakdown else
          ", ".join(f"{k} {v:.1f}" for k, v in breakdown.items()) + f"  (sum {sum(breakdown.values()):.1f})")
    system = CRITIC_V2.format(task=TASK, max_lessons=MAX_LESSONS_PER_ROUND, wildcard_rule=rule,
                              refinement_keys=", ".join(f'"{f["id"]}": "..."' for f in families))
    user = (f"Checker feedback on the champion (after this round):\n{fb}\n\n"
            f"Champion mean cost per dev day, by term: {bd}\n\n"
            "Families:\n" + "\n".join(fam_lines) + "\n\n"
            f"This round's attempts:\n{round_table}\n\n"
            "Shared lessons so far:\n" + ("\n".join(f"- {x}" for x in lessons) or "(none)"))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_critic_v2(text: str) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("no JSON object in critic output")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("critic output is not a JSON object")
    lessons = data.get("lessons", [])
    refinements = data.get("refinements", {})
    wildcard = data.get("wildcard")
    if not isinstance(lessons, list) or not isinstance(refinements, dict):
        raise ValueError("'lessons' must be a list and 'refinements' an object")
    if wildcard is not None and not isinstance(wildcard, dict):
        raise ValueError("'wildcard' must be an object or null")
    return {"lessons": [str(x).strip()[:MAX_HINT_CHARS] for x in lessons if str(x).strip()][:MAX_LESSONS_PER_ROUND],
            "refinements": {str(k): str(v).strip()[:MAX_HINT_CHARS] for k, v in refinements.items()},
            "wildcard": wildcard}


def apply_critic(families: list[dict], out: dict, eligible: str | None, r: int) -> tuple[list[dict], dict]:
    """Apply a parsed critic reply under the v2 rules. Returns (new families, what happened)."""
    families = [dict(f) for f in families]
    ids = {f["id"] for f in families}
    lessons, moved, missing, ignored = list(out["lessons"]), [], [], sorted(set(out["refinements"]) - ids)
    for f in families:
        line = out["refinements"].get(f["id"], "")
        if not line:
            missing.append(f["id"])  # keep the previous refinement; a family is never emptied or deleted
        elif CODING_FIX.search(line):
            moved.append(f["id"])
            lessons.append(line)  # coding fixes are shared lessons, never a hint slot
        else:
            f["refinement"] = line
    wildcard = {"proposed": out.get("wildcard"), "accepted": False, "reason": None}
    w = out.get("wildcard")
    if w:
        target, approach = str(w.get("replace", "")), str(w.get("approach", "")).strip()
        others = [f for f in families if f["id"] != target]
        sims = {f["id"]: round(similarity(approach, f["base"] + " " + f["refinement"]), 2) for f in others}
        if eligible is None:
            wildcard["reason"] = "no family eligible this round"
        elif target != eligible:
            wildcard["reason"] = f"only {eligible} may be replaced this round"
        elif not approach:
            wildcard["reason"] = "empty approach"
        elif CODING_FIX.search(approach):
            wildcard["reason"] = "a coding fix is not an approach"
        elif any(s > MAX_SIMILARITY for s in sims.values()):
            wildcard["reason"] = f"too similar to another family: {max(sims, key=sims.get)} ({max(sims.values())})"
        else:
            i = next(k for k, f in enumerate(families) if f["id"] == target)
            families[i] = {"id": f"W{r}", "name": "wildcard", "base": approach[:MAX_HINT_CHARS], "refinement": "",
                           "origin": f"wildcard from round {r}, replaced {target} ({families[i]['name']})",
                           "since_round": r + 1}
            wildcard.update(accepted=True, reason=str(w.get("why_different", ""))[:MAX_HINT_CHARS],
                            replaced=target, new_id=f"W{r}")
        wildcard["similarity"] = sims
    lessons = lessons[:MAX_LESSONS_PER_ROUND + len(moved)]
    return families, {"lessons": lessons, "refinements": {f["id"]: f["refinement"] for f in families},
                      "missing_refinements": missing, "coding_fixes_moved_to_lessons": moved,
                      "ignored_keys": ignored, "wildcard": wildcard}


def review(providers, families, memory, round_table, fb, breakdown, lessons, r, timeout=120.0) -> tuple[list[dict], dict]:
    """One critic v2 call. Returns (families for next round, record for the run file)."""
    eligible = wildcard_eligible(families, memory)
    messages = critic_messages(families, memory, round_table, fb, breakdown, lessons, eligible)
    out, tokens, p = _chat(providers, messages, timeout, 0.3, parse_critic_v2)
    families, rec = apply_critic(families, out, eligible, r)
    rec.update(tokens=tokens, provider=f"{p.name}:{p.model}", wildcard_eligible=eligible)
    return families, rec
