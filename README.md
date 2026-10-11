# DispatchIQ

**When a technician calls out sick and emergencies come in, re-plan the whole crew in one click.**

A team of AI agents writes and keeps improving the re-planning logic. A deterministic rule checker scores every schedule, and the AI never decides what is "best". Entry for c0mpiled-15 **Track 1** (self-improving agent team on Luminal). It fits YC's "New OS for the Physical World" request.

## The problem
Small HVAC, plumbing and electrical shops (2–15 techs) on Jobber or Housecall Pro re-plan by hand when the day breaks.
- **Housecall Pro:** "Optimize by Drive Time" only reorders jobs within one tech's day. It cannot move jobs between techs, and it is in alpha.
- **ServiceTitan:** costs about $245–500 per tech per month, plus setup (third-party estimates).

Competitors, market gap and sources: [MARKET.md](MARKET.md).

## How it works
```
generator.py   seeded day: 8-12 techs (skills, shifts), 30-50 booked jobs (windows, priority),
               then at 11:00-14:00: 1-2 techs out sick + 1-3 emergencies (2-hour promise)
simulate.py    fixed morning plan -> freeze jobs already started -> re-plan state -> CHECKER
               hard rules: no sick tech, skill match, each job once, every emergency assigned,
                           max overtime per tech
               cost = travel + Σ lateness×priority + overtime + 150×priority per job postponed
                      + 20 per customer moved between healthy techs + emergency wait minutes
sandbox.py     runs candidate code in a separate process (timeout, memory cap); scoring happens
               outside it, so a candidate cannot score itself
evolve.py      N agents per round write new replan() code (different strategy hints each);
               best on DEV days is promoted only if it also beats the champion on VALIDATION days
heldout.py     run once at the end on 50 HELD-OUT days whose hash is committed (HELDOUT_HASH.txt)
app.py         Streamlit: before/after schedule chart, metrics, improvement curve, held-out table
```

Policies:
- `policies/naive.py`: round-0 seed (what a busy dispatcher does).
- `policies/insertion.py`: textbook cheapest-insertion reference (non-AI).
- `policies/parametric.py`: knobs used by the no-LLM random-search baseline.

## Run
```bash
pip install -r requirements.txt
pytest -q                                          # 11 tests: checker math, rules, malformed input, sandbox, splits, LLM stub, research app

# Agents (Luminal first; any OpenAI-compatible provider works, fallbacks tried in order)
export LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=...          # Luminal (get at check-in)
export FALLBACK_1_BASE_URL=https://api.groq.com/openai/v1 FALLBACK_1_API_KEY=... FALLBACK_1_MODEL=...
export MONGODB_URI=...                                          # optional: rounds logged to Atlas
python evolve.py --rounds 8 --agents 6
python evolve.py --rounds 8 --agents 6 --mode random            # no-LLM ablation / offline test
python heldout.py                                               # ONCE, at the end
streamlit run app.py
```

## Reproduce

Every result is a file in `runs/<name>.json`, and `--name` refuses to overwrite one. Provider used for the LLM runs: Luminal, `deepseek-ai/DeepSeek-V4.1-Flash` (OpenAI-compatible, streamed; the gateway drops non-streamed requests that run past about 20 s).

```bash
export LLM_BASE_URL=https://flash.luminal.cloud/v1 LLM_MODEL=deepseek-ai/DeepSeek-V4.1-Flash LLM_API_KEY=...
# PowerShell: $env:LLM_BASE_URL="https://flash.luminal.cloud/v1"; $env:LLM_MODEL="deepseek-ai/DeepSeek-V4.1-Flash"; $env:LLM_API_KEY="..."

python evolve.py --mode random --rounds 8 --agents 6 --name random              # no LLM
python evolve.py               --rounds 8 --agents 6 --name llm-plain
python evolve.py --team        --rounds 8 --agents 6 --name llm-team
python evolve.py --team        --rounds 48 --agents 1 --name llm-team-1agent    # same 48 proposals, one at a time
python evolve.py --team        --rounds 8 --agents 1 --name llm-team-1agent-8r  # same rounds, one agent
python evolve.py --team        --rounds 8 --agents 6 --name llm-team-insertion \
                 --start dispatchiq/policies/insertion.py                       # only if llm-team does not beat random

python -m dispatchiq.scoreboard        # comparison table from the saved files (runs nothing)
streamlit run app.py                   # "Research runs" tab: same data as charts
```

- **Random search is deterministic.** With the same `--seed` (default 0) it reproduces exactly.
- **LLM runs are not.** Sampling uses temperature 0.7, so a rerun writes different code and gets different scores. The saved file is the record.

**Re-score a saved champion without any LLM.** The code saved in the run file is run through the same sandbox and checker. Dev and validation days are fixed, so the scores must match the file; a mismatch exits non-zero.

```bash
python rescore.py runs/llm-team.json                 # champion on dev + validation
python rescore.py runs/llm-team.json --code round0   # the starting policy
```

**Held-out days are not in `rescore.py`.** `python heldout.py runs/<name>.json` scores 50 held-out days once and writes `runs/heldout_result.json`.

### Final-solution rule (fixed 2026-10-11, before any held-out scoring)

The held-out run uses **the 6-agent LLM run with the lowest validation cost at 18:30 local time**.
- **Eligible runs:** `llm-plain`, `llm-team`, and `llm-team-insertion` if it was run. Each must have `--agents 6` and use the LLM.
- **Not eligible:** random search and the 1-agent runs.
- **Which cost counts:** the champion's validation cost in the run file as saved at 18:30. A run still going at 18:30 counts with the rounds it had saved by then.
- **One shot:** `heldout.py` is run once, at 18:30, on that file:

```bash
python -m dispatchiq.scoreboard     # last lines name the run this rule picks from the saved files
python heldout.py runs/<picked run>.json
```

No other run is scored on held-out days, and the rule is not changed after seeing held-out results.

## Results so far (offline, no LLM)
Random search over `parametric.py`, 6 rounds × 6 proposals, scored on 50 held-out days:

| Policy | Mean cost | On time |
|---|---|---|
| Dispatcher-style baseline (round 0) | 1589 | 58.9% |
| Textbook cheapest insertion | 1377 | 62.9% |
| Random-search champion | 1397 | 63.5% |

- Random search improves 12.1% on round 0, but **does not beat the textbook reference**.
- The bar for the LLM agent team on the day: beat **both** on the held-out days.
- If it doesn't, report that honestly. Judges reward a real number over a staged one.

## Honest limits
- Days are generated, not from a real shop. Travel is Manhattan distance at 2 min/km.
- The morning plan is fixed and identical for all policies. Only the re-plan is evolved.
- The cost weights (150, 20, 1) are product choices, published above. Changing them changes the "best" policy.
- The cost doesn't tell a booked customer apart from an unbooked one. A booked customer bumped off a healthy technician costs the same 150 × priority as a job that was never scheduled, and moving a job between healthy technicians costs only 20. A policy can trade booked customers for other jobs and still score better. We report both counts (`bumped`, `moved`) beside the cost but do not penalise them.
- The market claims come from search extracts and vendor marketing. Verify before putting them on slides.
