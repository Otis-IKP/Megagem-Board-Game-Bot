"""Tune a bot's numbers with a small genetic search on training deals.

    python -m arena.tune FairValuePacer [--pop 40 --gens 30]

Each candidate setting plays the same set of series against test opponents
(3, 4 and 5 players, all five charts, chart A twice). The series change every
generation so settings cannot memorise deals. The finalists are then re-scored
on a larger, separate validation set and the best is written to
results/tuned_<Bot>.json. Deal seeds used here are never used for final tests.
"""

import argparse
import json
import sys
import time
from random import Random

from arena import ROOT
from arena.engine import run_jobs, run_series, spec

from otis_bots.zoo import CLASS_BOTS, TRAIN_ZOO

WIN_BONUS = 15.0  # fitness = mean score + WIN_BONUS * win rate
TRAIN_POOL = TRAIN_ZOO + ("FairValuePacer",)
# Stronger pool for the second round of tuning: adds the two better bots.
STRONG_POOL = TRAIN_POOL + ("EvolvedWeights", "MarketReaderV1")
POOLS = {"train": TRAIN_POOL, "strong": STRONG_POOL, "class": CLASS_BOTS}
CHART_SLOTS = "AABCDE"
GAMES_PER_SERIES = 6

_REVEAL = ("reveal_sign", -1.0, 1.0)
SPACES = {
    "FairValuePacer": [
        ("share", 0.2, 1.2), ("lam0", 0.0, 2.0), ("kappa", -1.0, 2.0),
        ("delta", 0.0, 5.0), ("rho", 0.0, 0.8), ("inv_share", 0.0, 1.5),
        ("loan_share", 0.0, 1.5), _REVEAL,
    ],
    "MarketReader": [
        ("lam0", 0.0, 2.0), ("kappa", -1.0, 2.0), ("delta", 0.0, 5.0),
        ("rho", 0.0, 0.8), ("prior_weight", 0.2, 6.0), ("decay", 0.85, 1.0),
        _REVEAL,
    ],
    # Second round for the Market Reader: wider ranges, same parts as before.
    "mr_wide": [
        ("lam0", 0.0, 4.0), ("kappa", -1.5, 2.0), ("delta", -3.0, 5.0),
        ("rho", 0.0, 0.8), ("prior_weight", 0.2, 6.0), ("decay", 0.85, 1.0),
    ],
    # Wider ranges plus the optional parts that survived one-at-a-time tests.
    "mr_full": [
        ("lam0", 0.3, 4.0), ("kappa", -1.5, 1.5), ("delta", -3.0, 3.0),
        ("rho", 0.0, 0.8), ("prior_weight", 0.2, 6.0), ("decay", 0.85, 1.0),
        ("la_mix", 0.0, 0.6), ("win_cost", -3.0, 1.0), ("race_pen", 0.2, 1.0),
        ("deny_w", 0.0, 0.5),
    ],
    "EvolvedWeights": (
        [(f"w{i}", -1.0, 1.5) for i in range(5)]
        + [("w5", -1.0, 1.0), ("w6", -1.0, 1.5), ("w7", -3.0, 3.0)]
        + [(f"w{i}", -1.0, 1.5) for i in range(8, 12)]
        + [("w12", -1.0, 1.5), ("w13", -3.0, 5.0)]
        + [(f"w{i}", -0.5, 1.0) for i in range(14, 18)]
        + [("w18", -1.0, 1.5), ("w19", -3.0, 3.0)]
        + [("rho", 0.0, 0.8), _REVEAL]
    ),
}


SPACE_BOT = {"mr_wide": "MarketReader", "mr_full": "MarketReader"}
# by_n is cleared so the values being tuned are not overridden per player count.
FIXED = {"mr_full": {"reset_detect": 1.0, "la_share": 6.0, "by_n": None}}


def to_params(bot: str, vec: list[float]) -> dict:
    out, weights = dict(FIXED.get(bot, {})), []
    for (name, _, _), x in zip(SPACES[bot], vec):
        if name == "reveal_sign":
            out[name] = float(round(x))
        elif name.startswith("w") and name[1:].isdigit():
            weights.append(x)
        else:
            out[name] = x
    if weights:
        out["w"] = tuple(weights)
    return out


def default_vec(bot: str, players=None) -> list[float]:
    from arena.engine import make_class

    params = {**make_class(spec(SPACE_BOT.get(bot, bot))).PARAMS, **FIXED.get(bot, {})}
    by_n = make_class(spec(SPACE_BOT.get(bot, bot))).PARAMS.get("by_n") or {}
    if players and len(players) == 1 and players[0] in by_n:
        params = {**params, **by_n[players[0]]}  # start from that count's settings
    vec = []
    for name, _, _ in SPACES[bot]:
        if name.startswith("w") and name[1:].isdigit():
            vec.append(params["w"][int(name[1:])])
        else:
            vec.append(params[name])
    return vec


def lineups(seed: int, repeats: int, pool=TRAIN_POOL, seed_base=1_000_000,
            players=(3, 4, 5)):
    """Deterministic list of (n, chart, opponents, my seat, deal seeds)."""
    rng = Random(seed)
    out = []
    for rep in range(repeats):
        for n in players:
            for chart in CHART_SLOTS:
                if pool is CLASS_BOTS:  # real entrants meet at most once per table
                    opps = rng.sample(pool, n - 1)
                else:
                    opps = [rng.choice(pool) for _ in range(n - 1)]
                first = seed_base + rng.randrange(10**6) * 10
                seeds = list(range(first, first + GAMES_PER_SERIES))
                out.append((n, chart, opps, rng.randrange(n), seeds))
    return out


def evaluate(task: tuple) -> tuple[float, float]:
    """(mean score per game, win rate) for one setting over a set of series."""
    bot, params, seed, repeats, seed_base = task[:5]
    pool = POOLS[task[5]] if len(task) > 5 else TRAIN_POOL
    players = task[6] if len(task) > 6 else (3, 4, 5)
    bot = SPACE_BOT.get(bot, bot)
    total = wins = games = 0
    for n, chart, opps, seat, seeds in lineups(seed, repeats, pool, seed_base, players):
        specs = [spec(o) for o in opps]
        specs.insert(seat, spec(bot, params))
        out = run_series({"specs": specs, "chart": chart, "seeds": seeds})
        for scores, winners in zip(out["scores"], out["winners"]):
            total += scores[seat]
            wins += (seat in winners) / len(winners)
            games += 1
    return total / games, wins / games


def fitness(result: tuple[float, float]) -> float:
    return result[0] + WIN_BONUS * result[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bot", choices=list(SPACES))
    ap.add_argument("--pool", choices=list(POOLS), default="train")
    ap.add_argument("--players", type=int, nargs="+", default=[3, 4, 5])
    ap.add_argument("--out", default=None)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--gens", type=int, default=30)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    bot, space = args.bot, SPACES[args.bot]
    rng = Random(args.seed)
    lo = [s[1] for s in space]
    hi = [s[2] for s in space]
    clip = lambda v: [min(h, max(l, x)) for x, l, h in zip(v, lo, hi)]  # noqa: E731

    base = default_vec(bot, args.players)
    pop = [base] + [
        clip([x + rng.gauss(0, 0.25 * (h - l)) for x, l, h in zip(base, lo, hi)])
        for _ in range(args.pop - 1)
    ]
    finalists = [base]
    start = time.time()
    for gen in range(args.gens):
        tasks = [(bot, to_params(bot, v), 10_000 + gen, args.repeats, 1_000_000,
                  args.pool, tuple(args.players)) for v in pop]
        scored = sorted(
            zip((fitness(r) for r in run_jobs(tasks, args.workers, evaluate)), pop),
            key=lambda t: -t[0],
        )
        fits = [f for f, _ in scored]
        print(f"gen {gen:2d}  best {fits[0]:6.2f}  median {fits[len(fits)//2]:6.2f}  "
              f"{time.time()-start:5.0f}s", flush=True)
        finalists.append(scored[0][1])
        elites = [v for _, v in scored[:4]]
        sigma = 0.12 * (1.0 - 0.7 * gen / max(1, args.gens - 1))
        nxt = list(elites)
        while len(nxt) < args.pop:
            a = max(rng.sample(scored, 3), key=lambda t: t[0])[1]
            b = max(rng.sample(scored, 3), key=lambda t: t[0])[1]
            child = []
            for x, y, l, h in zip(a, b, lo, hi):
                t = rng.random()
                z = t * x + (1 - t) * y
                if rng.random() < 0.3:
                    z += rng.gauss(0, sigma * (h - l))
                child.append(z)
            nxt.append(clip(child))
        pop = nxt
    finalists += [v for v in pop[:6]]
    # Validation on separate deals: 8 repeats = 144 series = 864 games each.
    uniq = [list(t) for t in {tuple(round(x, 6) for x in v) for v in finalists}]
    val_reps = 8 * 3 // len(args.players)
    extra = (args.pool, tuple(args.players))
    tasks = [(bot, to_params(bot, v), 777, val_reps, 2_000_000) + extra for v in uniq]
    results = run_jobs(tasks, args.workers, evaluate)
    base_res = evaluate((bot, to_params(bot, base), 777, val_reps, 2_000_000) + extra)
    best_i = max(range(len(uniq)), key=lambda i: fitness(results[i]))
    out = {
        "bot": bot,
        "params": to_params(bot, uniq[best_i]),
        "validation": {"mean_score": results[best_i][0], "win_rate": results[best_i][1]},
        "untuned_validation": {"mean_score": base_res[0], "win_rate": base_res[1]},
        "search": {"pop": args.pop, "gens": args.gens, "repeats": args.repeats,
                   "seed": args.seed, "win_bonus": WIN_BONUS,
                   "pool": args.pool, "players": args.players,
                   "finalists_validated": len(uniq)},
    }
    path = ROOT / "results" / f"tuned_{args.out or bot}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["validation"]), "untuned:", json.dumps(out["untuned_validation"]))
    print(f"wrote {path}")


if __name__ == "__main__":
    sys.exit(main())
