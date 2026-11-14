"""Final tests on deals never used for tuning. Writes results/evaluation.json.

    python -m arena.evaluate            # full run (a few minutes on 8 cores)
    python -m arena.evaluate --quick    # about a tenth of the games

A "series" copies the tournament: one fixed seating plays 15 games in a row and
every bot keeps its memory between games. All comparisons between candidates
use the same seatings, opponents and deals.
"""

import argparse
import itertools
import json
import time
from random import Random

from arena import ROOT
from arena.engine import run_jobs, spec

from otis_bots.zoo import ALL_ZOO, HOLDOUT_ZOO

CANDIDATES = ("FairValuePacer", "MarketReader", "EvolvedWeights")
REFERENCES = ("HeuristicBot", "ThirdValueBot")
GAMES = 15
TEST_SEED_BASE = 5_000_000


def _seeds(rng: Random) -> list[int]:
    first = TEST_SEED_BASE + rng.randrange(10**6) * 20
    return list(range(first, first + GAMES))


def summarise(rows: list[dict]) -> dict:
    """rows: one per series with 'score' (list per game) and 'win' (list)."""
    games = sum(len(r["score"]) for r in rows)
    mean = sum(sum(r["score"]) for r in rows) / games
    win = sum(sum(r["win"]) for r in rows) / games
    return {"series": len(rows), "games": games, "mean_score": mean, "win_rate": win}


def bootstrap(values: list[float], reps: int = 2000, seed: int = 1) -> list[float]:
    """95% interval for the mean of per-series values (resampling series)."""
    rng = Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(reps))
    return [means[int(0.025 * reps)], means[int(0.975 * reps)]]


def series_rows(out: dict, seat: int) -> dict:
    return {
        "score": [g[seat] for g in out["scores"]],
        "win": [(seat in w) / len(w) for w in out["winners"]],
        "opp": [
            (sum(g) - g[seat]) / (len(g) - 1) for g in out["scores"]
        ],
    }


# ----------------------------------------------------------------- E1 field


def field_test(entrants, pool, per_cell: int, workers: int, seed: int) -> dict:
    """Each entrant takes the same seat against the same sampled opponents."""
    rng = Random(seed)
    slots = []
    for n in (3, 4, 5):
        for chart in "ABCDE":
            for _ in range(per_cell):
                opps = [rng.choice(pool) for _ in range(n - 1)]
                slots.append((n, chart, opps, rng.randrange(n), _seeds(rng)))
    jobs = []
    for e in entrants:
        for i, (n, chart, opps, seat, seeds) in enumerate(slots):
            specs = [spec(o) for o in opps]
            specs.insert(seat, spec(e))
            jobs.append({"specs": specs, "chart": chart, "seeds": seeds,
                         "tag": (e, i, n, seat)})
    outs = run_jobs(jobs, workers)
    data = {e: {} for e in entrants}
    for out in outs:
        e, i, n, seat = out["tag"]
        data[e][i] = {**series_rows(out, seat), "n": n, "chart": out["chart"]}
    report = {"slots": len(slots), "entrants": {}}
    for e in entrants:
        rows = [data[e][i] for i in range(len(slots))]
        entry = summarise(rows)
        entry["score_ci"] = bootstrap([sum(r["score"]) / GAMES for r in rows])
        entry["margin_vs_table"] = sum(
            sum(r["score"]) - sum(r["opp"]) for r in rows
        ) / (len(rows) * GAMES)
        entry["by_players"] = {
            str(n): summarise([r for r in rows if r["n"] == n]) for n in (3, 4, 5)
        }
        entry["by_chart"] = {
            c: summarise([r for r in rows if r["chart"] == c]) for c in "ABCDE"
        }
        entry["by_game_index"] = [
            sum(r["score"][g] for r in rows) / len(rows) for g in range(GAMES)
        ]
        report["entrants"][e] = entry
    report["paired"] = {}
    for a, b in itertools.combinations(entrants, 2):
        diffs = [
            (sum(data[a][i]["score"]) - sum(data[b][i]["score"])) / GAMES
            for i in range(len(slots))
        ]
        report["paired"][f"{a} - {b}"] = {
            "mean_diff": sum(diffs) / len(diffs),
            "ci": bootstrap(diffs),
            "share_of_series_ahead": sum(d > 0 for d in diffs) / len(diffs),
        }
    return report


# ---------------------------------------------------------- E2 head to head


def head_to_head(per_cell: int, workers: int, seed: int) -> dict:
    """All three candidates at one table, every seat order, fillers for 4-5."""
    rng = Random(seed)
    jobs = []
    for n in (3, 4, 5):
        for chart in "ABCDE":
            for _ in range(per_cell):
                fill = [rng.choice(ALL_ZOO) for _ in range(n - 3)]
                seeds = _seeds(rng)
                for perm in itertools.permutations(CANDIDATES):
                    names = list(perm) + fill
                    jobs.append({"specs": [spec(x) for x in names], "chart": chart,
                                 "seeds": seeds, "tag": (n, names)})
    outs = run_jobs(jobs, workers)
    report = {}
    for scope in ("all", "3", "4", "5"):
        rows = {c: [] for c in CANDIDATES}
        for out in outs:
            n, names = out["tag"]
            if scope != "all" and str(n) != scope:
                continue
            for c in CANDIDATES:
                rows[c].append(series_rows(out, names.index(c)))
        report[scope] = {c: summarise(r) for c, r in rows.items()}
        if scope == "all":
            for c in CANDIDATES:
                report[scope][c]["score_ci"] = bootstrap(
                    [sum(r["score"]) / GAMES for r in rows[c]]
                )
    return report


# ------------------------------------------------------- E3 one vs copies


def one_vs_copies(names, per_cell: int, workers: int, seed: int) -> dict:
    """Row bot against n-1 copies of the column bot, 3 and 4 players."""
    rng = Random(seed)
    slots = [(n, chart, rng.randrange(n), _seeds(rng))
             for n in (3, 4) for chart in "ABCDE" for _ in range(per_cell)]
    jobs = []
    for a in names:
        for b in names:
            for n, chart, seat, seeds in slots:
                specs = [spec(b)] * (n - 1)
                specs.insert(seat, spec(a))
                jobs.append({"specs": specs, "chart": chart, "seeds": seeds,
                             "tag": (a, b, seat)})
    cells = {}
    for out in run_jobs(jobs, workers):
        a, b, seat = out["tag"]
        cells.setdefault((a, b), []).append(series_rows(out, seat))
    return {
        a: {b: {k: v for k, v in summarise(cells[(a, b)]).items()
                if k in ("mean_score", "win_rate")}
            | {"margin": sum(sum(r["score"]) - sum(r["opp"]) for r in cells[(a, b)])
               / (len(cells[(a, b)]) * GAMES)}
            for b in names}
        for a in names
    }


# --------------------------------------------------------- E4 league table


def league(pool, combos_per_n: int, chart: str, workers: int, seed: int) -> dict:
    """Round-robin style: random distinct line-ups from the pool, as the
    organiser plans to run. Reports points per game and win rate per bot."""
    rng = Random(seed)
    jobs = []
    for n in (3, 4, 5):
        for _ in range(combos_per_n):
            names = rng.sample(pool, n)
            jobs.append({"specs": [spec(x) for x in names], "chart": chart,
                         "seeds": _seeds(rng), "tag": names})
    rows = {b: [] for b in pool}
    for out in run_jobs(jobs, workers):
        for seat, name in enumerate(out["tag"]):
            rows[name].append(series_rows(out, seat))
    table = {b: summarise(r) for b, r in rows.items()}
    return dict(sorted(table.items(), key=lambda kv: -kv[1]["mean_score"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    k = 0.1 if args.quick else 1.0
    cells = lambda x: max(2, int(x * k))  # noqa: E731
    start = time.time()
    report = {"games_per_series": GAMES, "quick": args.quick}

    def step(name, fn):
        report[name] = fn()
        print(f"{name} done at {time.time() - start:.0f}s", flush=True)

    entrants = CANDIDATES + REFERENCES
    step("field_all_opponents", lambda: field_test(entrants, ALL_ZOO, cells(40), args.workers, 101))
    step("field_unseen_opponents", lambda: field_test(entrants, HOLDOUT_ZOO, cells(20), args.workers, 102))
    step("head_to_head", lambda: head_to_head(cells(10), args.workers, 103))
    step("one_vs_copies", lambda: one_vs_copies(
        CANDIDATES + ("HeuristicBot", "ThirdValueBot", "AggressiveBot"), cells(6), args.workers, 104))
    for cand in CANDIDATES:
        step(f"league_chartA_{cand}", lambda c=cand: league(
            (c,) + ALL_ZOO, cells(300), "A", args.workers, 105))
    step("league_chartA_all_three", lambda: league(
        CANDIDATES + ALL_ZOO, cells(400), "A", args.workers, 106))
    name = "evaluation_quick.json" if args.quick else "evaluation.json"
    (ROOT / "results" / name).write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote results/{name} in {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
