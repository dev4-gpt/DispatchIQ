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
- The market claims come from search extracts and vendor marketing. Verify before putting them on slides.
