"""Simulate the real tournament: my bot among the classmates' submitted bots.

    python -m arena.class_field league [MarketReader ...]   # league table
    python -m arena.class_field slow                        # small SamplingBot test

Line-ups are random sets of distinct bots, as the organiser plans to run,
over 3, 4 and 5 players and all five charts, 15 games per seating.
"""

import json
import sys
from random import Random

from arena import ROOT
from arena.engine import run_jobs, spec
from arena.evaluate import GAMES, bootstrap

from otis_bots.zoo import CLASS_BOTS, SLOW_CLASS_BOTS

SEED_BASE = 8_000_000


def short(name: str) -> str:
    return name.split(":")[-1]


def league(pool, per_cell: int, seed: int, workers: int = 8, games: int = GAMES,
           must_include=None, seed_base: int = SEED_BASE) -> dict:
    rng = Random(seed)
    jobs = []
    for n in (3, 4, 5):
        for chart in "ABCDE":
            for _ in range(per_cell):
                if must_include:
                    rest = [b for b in pool if b != must_include]
                    names = rng.sample(rest, n - 1)
                    names.insert(rng.randrange(n), must_include)
                else:
                    names = rng.sample(pool, n)
                first = seed_base + rng.randrange(10**6) * 20
                jobs.append({"specs": [spec(x) for x in names], "chart": chart,
                             "seeds": list(range(first, first + games)), "tag": names})
    rows = {b: [] for b in pool}
    for out in run_jobs(jobs, workers):
        n = len(out["tag"])
        for seat, name in enumerate(out["tag"]):
            score = sum(g[seat] for g in out["scores"]) / len(out["scores"])
            win = sum((seat in w) / len(w) for w in out["winners"]) / len(out["scores"])
            rows[name].append((score, win, n, out["chart"]))
    table = {}
    for b, r in rows.items():
        if not r:
            continue
        table[short(b)] = {
            "series": len(r),
            "points": sum(x[0] for x in r) / len(r),
            "ci": bootstrap([x[0] for x in r]),
            "win_rate": sum(x[1] for x in r) / len(r),
            "by_n": {k: sum(x[0] for x in r if x[2] == k) / max(1, sum(x[2] == k for x in r)) for k in (3, 4, 5)},
            "chart_A": sum(x[0] for x in r if x[3] == "A") / max(1, sum(x[3] == "A" for x in r)),
            "chart_A_wins": sum(x[1] for x in r if x[3] == "A") / max(1, sum(x[3] == "A" for x in r)),
        }
    return dict(sorted(table.items(), key=lambda kv: -kv[1]["points"]))


def show(table: dict) -> None:
    print("| Rank | Bot | Points per game | 95% range | Win rate | 3p | 4p | 5p | Chart A points | Chart A wins |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for i, (b, d) in enumerate(table.items()):
        print(f"| {i + 1} | {b} | {d['points']:.1f} | {d['ci'][0]:.1f} to {d['ci'][1]:.1f} | "
              f"{100 * d['win_rate']:.1f}% | " + " | ".join(f"{d['by_n'][k]:.1f}" for k in (3, 4, 5))
              + f" | {d['chart_A']:.1f} | {100 * d['chart_A_wins']:.1f}% |")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "league"
    mine = sys.argv[2:] or ["MarketReader"]
    if mode == "slow":
        pool = tuple(mine) + CLASS_BOTS + SLOW_CLASS_BOTS
        table = league(pool, 2, 81, games=5, must_include=SLOW_CLASS_BOTS[0])
        name = "class_field_slow.json"
    else:
        pool = tuple(mine) + CLASS_BOTS
        table = league(pool, 40, 80)
        name = "class_field_" + "_".join(mine) + ".json"
    show(table)
    (ROOT / "results" / name).write_text(json.dumps(table, indent=1) + "\n")


if __name__ == "__main__":
    main()
