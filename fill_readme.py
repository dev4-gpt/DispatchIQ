"""Fill the marked blanks in README.md from saved files. Run after heldout.py (18:30).

    python fill_readme.py --check   # show what would change; write nothing
    python fill_readme.py           # write README.md

Blocks are delimited by HTML comments, for example
    <!-- BEGIN heldout-table --> ... <!-- END heldout-table -->
Only the text between the markers is replaced; a block whose data does not exist yet is left as is
and reported. Every number comes from runs/heldout_result.json or the run files (via the scoreboard).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dispatchiq import scoreboard

ROOT = Path(__file__).resolve().parent


def _f(x, spec, dash="-"):
    return dash if x is None else format(x, spec)


def heldout_table(runs_dir: Path, runs: dict) -> str | None:
    rows, note = scoreboard.heldout_rows(runs_dir, runs)
    if not rows:
        return None
    out = ["| Policy | Held-out cost | vs naive | On-time | Missed promises | Booked bumped | Moved | Infeasible days | Validation cost |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        name = f"**{r['policy']} (final solution)**" if r.get("final_solution") else r["policy"]
        out.append(f"| {name} | {r['mean_cost']:.1f} | {_f(r.get('vs_round0_pct'), '+.1f')}% | "
                   f"{_f(r.get('on_time_pct'), '.1f')}% | {r.get('missed_promises')}/{r.get('emergencies')} | "
                   f"{_f(r.get('bumped_booked'), 'd')} | {_f(r.get('moved_healthy'), 'd')} | {r.get('infeasible')} | "
                   f"{_f(r.get('validation_cost'), '.1f')} |")
    out.append("")
    out.append(f"50 held-out days (seeds 1000-1049), scored once by `heldout.py`: {note}.")
    return "\n".join(out)


def heldout_headline(runs_dir: Path, runs: dict) -> str | None:
    rows, _ = scoreboard.heldout_rows(runs_dir, runs)
    final = next((r for r in rows if r.get("final_solution")), None)
    if final is None:
        return None
    return (f"**Held-out (50 unseen days):** the final solution, **{final['policy']}**, costs "
            f"**{final['mean_cost']:.1f}**, **{final['vs_round0_pct']:.1f}% lower than the naive baseline** "
            f"(validation: {final.get('validation_cost'):.1f}).")


def single_agent(runs_dir: Path, runs: dict) -> str | None:
    par = {p["run"]: p for p in scoreboard.parallelism(runs)}
    one, six = par.get("LLM team v2, 1 agent"), par.get("LLM team v2")
    if not one or one["status"] == "not run" or one["status"].startswith("in progress"):
        return None  # only fill once the single-agent run has finished or stopped
    out = ["| Run | Agents | Rounds | Validation at round 8 | Wall-clock at round 8 | Final validation | "
           "Wall-clock at end | First beat insertion | First beat random search | Status |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for p in (six, one):
        out.append(f"| {p['run']} | {p['agents']} | {p['rounds']} | {_f(p['val_at_round_8'], '.1f')} | "
                   f"{_f(p['seconds_at_round_8'], '.0f')} s | {p['points'][-1][1]:.1f} | {p['total_seconds']:.0f} s | "
                   f"{_f(p['seconds_to_beat_insertion'], '.0f')} s | {_f(p['seconds_to_beat_random'], '.0f')} s | {p['status']} |")
    return "\n".join(out)


BLOCKS = {"heldout-table": heldout_table, "heldout-headline": heldout_headline, "single-agent": single_agent}


def fill(text: str, runs_dir: Path) -> tuple[str, dict[str, str]]:
    runs = scoreboard.load_runs(runs_dir)
    report = {}
    for name, build in BLOCKS.items():
        pattern = re.compile(rf"(<!-- BEGIN {name} -->\n)(.*?)(\n<!-- END {name} -->)", re.S)
        if not pattern.search(text):
            report[name] = "marker missing"
            continue
        body = build(runs_dir, runs)
        if body is None:
            report[name] = "no data yet; left blank"
            continue
        text = pattern.sub(lambda m: m.group(1) + body + m.group(3), text)
        report[name] = "filled"
    return text, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only; do not write README.md")
    args = ap.parse_args(argv)
    readme = ROOT / "README.md"
    old = readme.read_text(encoding="utf-8")
    new, report = fill(old, ROOT / "runs")
    for name, status in report.items():
        print(f"{name:18s} {status}")
    if args.check:
        print("check only: README.md not written" + (" (would change)" if new != old else " (no change)"))
        return 0
    if new != old:
        readme.write_text(new, encoding="utf-8")
        print("README.md updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
