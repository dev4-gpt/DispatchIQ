# Market and research gap

These facts come from search extracts of the linked pages, vendor marketing and third-party estimates. Verify each one before quoting it.

## Who has the problem
Small HVAC, plumbing and electrical shops with 2–15 technicians. When a tech calls in sick or an emergency arrives mid-day, someone re-plans the whole crew by hand.

## What exists today
| Product | What it does for a disrupted day | Gap |
|---|---|---|
| **Housecall Pro**: "Optimize by Drive Time" | Reorders jobs **within one tech's day** only; doesn't move jobs between techs; alpha, limited group ([help article](https://help.housecallpro.com/en/articles/14093813-optimize-by-drive-time)) | No cross-tech re-plan when someone is out |
| **Jobber** | Built-in routing and an AI dispatch add-on. One user with ~70 clients spent 5 hours on routing setup ([community](https://community.getjobber.com/tag/map%20view)); Capterra reviewers call workflows restrictive | Manual effort at scale |
| **ServiceTitan** | Enterprise dispatch. Estimated ~$245–500 per tech per month plus $2k–50k setup; reviewers say it's hard to justify below ~15 techs ([projul](https://projul.com/blog/servicetitan-pricing-analysis-2026), [getonecrew](https://www.getonecrew.com/post/servicetitan-pricing)) | Too expensive for small shops |
| **FieldCamp, Fieldproxy** | *Claim* AI re-dispatch, including a sick tech's day, and plug into the tools above ([FieldCamp](https://fieldcamp.ai/ai-dispatcher.md), [Fieldproxy](https://www.fieldproxy.ai/blog/best-hvac-software-ai-scheduling-dispatch-2026)) | Vendor marketing, not independently verified |

**Our wedge:** a one-click team re-plan for shops on Jobber or Housecall Pro. It keeps customer churn low, keeps a human approval step, and shows a score for every schedule.

## Research gap (the Track 1 "difficulty" claim)
- LLM-driven heuristic design already works on routing benchmarks:
  - EoH, ReEvo and EoH-S (AAAI 2026), on TSP, CVRP and bin packing;
  - VRPAgent ([arXiv 2510.07073](https://arxiv.org/abs/2510.07073v1));
  - RAISE ([arXiv 2606.31801](https://arxiv.org/pdf/2606.31801)).
- **We found no published work evolving re-plan policies for technician routing with skills, time windows and mid-day disruptions.** The search was limited, so say "we found none", not "first ever".
- Technician routing benchmarks exist (Pillac et al.; Xie, Potts and Bektaş). This prototype uses its own seeded generator, with dev, validation and held-out splits.
