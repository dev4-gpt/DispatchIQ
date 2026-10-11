# DispatchIQ: 6-hour runbook (Track 1)

The code already runs end to end offline. The day is about **real agents, real rounds, one honest held-out result and a clear demo**.

## Check-in (first 20 minutes)
- Get the **Luminal** base URL, model names (DeepSeek or GLM Flash), concurrency limits and context length. Test it with `python evolve.py --rounds 1 --agents 1`.
- Confirm the Track 1 rules: baseline, rounds, fresh held-out tests, and the submission format.
- Declare this pre-built prototype on the form if the rules require it.
- Set a fallback provider (Groq or Cerebras) and `MONGODB_URI` (MongoDB prize).

## Roles
| Who | Job |
|---|---|
| A (agents) | Run `evolve.py`; tune strategy hints in `proposers.py` (STRATEGIES, TASK prompt); watch errors |
| B (checker and sim) | Keep the checker honest; add realism if time allows (e.g. tech home bases, lunch breaks); never touch held-out |
| C (UI and pitch) | `app.py` polish, slides, backup video; 3 calls with field-service owners for quotes |

## Timeline
| Time | Do | Done when |
|---|---|---|
| 0:00–0:30 | Luminal test, 1 round with 2 agents | LLM proposals pass the sandbox |
| 0:30–2:00 | 4–6 rounds with 6 agents; read failures; fix prompt hints | Validation cost below round 0 |
| 2:00–3:30 | Longer run (10+ rounds); ablation: `--agents 1` vs `--agents 6` and `--mode random` | **Checkpoint: LLM champion beats random search and insertion on validation** |
| 3:30–5:00 | If not, use the fallback: add `insertion.py` as the `--start` seed and evolve from it (`--start dispatchiq/policies/insertion.py`) | Champion beats both on validation |
| 5:00–5:30 | **`python heldout.py` once.** Screenshot the table | Held-out result saved |
| 5:30–6:00 | Record the demo video; submit to Track 1, MongoDB and Luminal credits | Submitted |

## 90-second demo
1. "Small shops re-plan by hand when a tech calls in sick. Housecall Pro's optimizer can't even move jobs between techs."
2. Toggle the disruption on a held-out day, and show round 0 vs the evolved champion side by side.
3. The improvement curve over rounds, plus the ablation (6 agents vs 1, LLM vs random search).
4. The held-out table on 50 unseen days, with the committed hash.
5. "Agents propose, the checker decides. Next: plug into Jobber and Housecall Pro as a one-click re-plan add-on."

## If things break
| Problem | Do |
|---|---|
| Luminal slow or limited | Fewer agents per round, and set the fallback provider |
| Agents keep failing hard rules | Show them the checker's violation text (already in the feedback); add an example to TASK |
| Curve flat | Seed from `insertion.py`, raise rounds, add the local-search strategy hint |
| Streamlit issue | Show `heldout.py` output plus the run JSON; use the backup video |
