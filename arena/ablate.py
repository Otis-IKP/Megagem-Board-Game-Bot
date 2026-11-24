"""Test one change at a time: each variant plays the same series as the
baseline Market Reader, and the paired difference is reported.

    python -m arena.ablate              # the built-in list of variants
    python -m arena.ablate --series 20  # series per (players, chart) cell

Uses its own deals (not the tuning or final-test deals).
"""

import argparse
import json
from random import Random

from arena import ROOT
from arena.engine import run_jobs, spec
from arena.evaluate import GAMES, bootstrap

from otis_bots.zoo import ALL_ZOO, CLASS_BOTS

POOL = ALL_ZOO + ("EvolvedWeights", "MarketReaderV1", "FairValuePacer")
SEED_BASE = 3_000_000

VARIANTS = {
    "look-ahead mix 0.5": {"la_mix": 0.5},
    "look-ahead mix 1.0": {"la_mix": 1.0},
    "look-ahead 1.0, share 0.4": {"la_mix": 1.0, "la_share": 0.4},
    "look-ahead 1.0, share 1.0": {"la_mix": 1.0, "la_share": 1.0},
    "infer hands k=0.5": {"color_k": 0.5},
    "infer hands k=1.5": {"color_k": 1.5},
    "infer hands k=3": {"color_k": 3.0},
    "split 1-gem / 2-gem lots": {"split_lots": 1.0},
    "all-in bids as lower bound": {"censor": 1.0},
    "reset on behaviour change": {"reset_detect": 1.0},
    "mission supply check": {"supply_check": 1.0},
    "mission race penalty 0.5": {"race_pen": 0.5},
    "mission race penalty 0.2": {"race_pen": 0.2},
    "mission deny 0.3": {"deny_w": 0.3},
    "mission deny 0.6": {"deny_w": 0.6},
    "win cost 0.5": {"win_cost": 0.5},
    "win cost 1.0": {"win_cost": 1.0},
    "win cost 2.0": {"win_cost": 2.0},
}


def make_slots(per_cell: int, seed: int, pool=POOL, rotate: bool = False,
               seed_base: int = SEED_BASE):
    rng = Random(seed)
    slots = []
    for n in (3, 4, 5):
        for chart in "ABCDE":
            for _ in range(per_cell):
                opps = [rng.choice(pool) for _ in range(n - 1)]
                first = seed_base + rng.randrange(10**6) * 20
                slots.append({"n": n, "chart": chart, "opps": opps,
                              "seat": rng.randrange(n),
                              "seeds": list(range(first, first + GAMES)),
                              "rotate": rotate})
    return slots


def compare(variants: dict, slots: list, workers: int, bot: str = "MarketReader") -> dict:
    """Paired results for each variant against the first entry (the baseline)."""
    jobs = []
    for name, params in variants.items():
        for i, s in enumerate(slots):
            specs = [spec(o) for o in s["opps"]]
            specs.insert(s["seat"], spec(*params) if isinstance(params, tuple) else spec(bot, params or None))
            job = {"specs": specs, "chart": s["chart"], "seeds": s["seeds"],
                   "tag": (name, i, s["seat"])}
            if s["rotate"]:
                job.update(rotate_at=GAMES // 2, keep=s["seat"])
            jobs.append(job)
    score = {name: {} for name in variants}
    wins = {name: {} for name in variants}
    for out in run_jobs(jobs, workers):
        name, i, seat = out["tag"]
        score[name][i] = sum(g[seat] for g in out["scores"]) / GAMES
        wins[name][i] = sum((seat in w) / len(w) for w in out["winners"]) / GAMES
    names = list(variants)
    base = names[0]
    n = len(slots)
    report = {}
    for name in names:
        diffs = [score[name][i] - score[base][i] for i in range(n)]
        report[name] = {
            "points": sum(score[name].values()) / n,
            "win_rate": sum(wins[name].values()) / n,
            "diff": sum(diffs) / n,
            "ci": bootstrap(diffs) if name != base else [0.0, 0.0],
            "by_n": {
                str(k): sum(d for d, s in zip(diffs, slots) if s["n"] == k)
                / max(1, sum(s["n"] == k for s in slots)) for k in (3, 4, 5)
            },
        }
    return report


def show(report: dict) -> None:
    print("| Variant | Points per game | Change | 95% range | Win rate | 3p | 4p | 5p |")
    print("|---|---|---|---|---|---|---|---|")
    for name, r in report.items():
        print(f"| {name} | {r['points']:.1f} | {r['diff']:+.2f} | "
              f"{r['ci'][0]:+.2f} to {r['ci'][1]:+.2f} | {100 * r['win_rate']:.1f}% | "
              + " | ".join(f"{r['by_n'][k]:+.1f}" for k in "345") + " |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", type=int, default=30)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="ablation_single.json")
    args = ap.parse_args()
    variants = {"baseline": {}, **VARIANTS}
    report = compare(variants, make_slots(args.series, 301), args.workers)
    show(report)
    # The reset switch only matters when seats change mid-series.
    print("\nWith opponents swapping seats half-way through each series:")
    rot = compare({"baseline": {}, "reset on behaviour change": {"reset_detect": 1.0}},
                  make_slots(args.series, 302, rotate=True), args.workers)
    show(rot)
    (ROOT / "results" / args.out).write_text(
        json.dumps({"fixed_seats": report, "swapped_seats": rot}, indent=1) + "\n")


if __name__ == "__main__":
    main()
