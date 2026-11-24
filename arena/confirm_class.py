"""Paired check: current Market Reader settings against the class-tuned ones.

    python -m arena.confirm_class [series per cell]

Both play the same fresh deals (not used in tuning) against random line-ups
of distinct submitted bots, then against the older stand-in opponents.
"""

import json
import sys
from random import Random

from arena import ROOT
from arena.ablate import POOL, compare, make_slots, show
from arena.evaluate import GAMES

from otis_bots.market_reader_v2_base import BY_N_V2
from otis_bots.zoo import CLASS_BOTS

KEYS = ("lam0", "kappa", "delta", "rho", "prior_weight", "decay", "la_mix",
        "win_cost", "race_pen", "deny_w")


def tuned_by_n() -> dict:
    out = {}
    for n in (3, 4, 5):
        p = json.loads((ROOT / "results" / f"tuned_mr_class_n{n}.json").read_text())["params"]
        out[n] = {k: round(p[k], 3) for k in KEYS}
    return out


def class_slots(per_cell: int, seed: int, seed_base: int) -> list:
    rng = Random(seed)
    slots = []
    for n in (3, 4, 5):
        for chart in "ABCDE":
            for _ in range(per_cell):
                first = seed_base + rng.randrange(10**6) * 20
                slots.append({"n": n, "chart": chart,
                              "opps": rng.sample(CLASS_BOTS, n - 1),
                              "seat": rng.randrange(n),
                              "seeds": list(range(first, first + GAMES)),
                              "rotate": False})
    return slots


def main() -> None:
    per_cell = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    new = tuned_by_n()
    old = BY_N_V2
    blend = {n: {k: round((new[n][k] + old[n][k]) / 2, 3) for k in KEYS} for n in new}
    variants = {"current": {"by_n": BY_N_V2}, "class-tuned": {"by_n": new}, "half-way": {"by_n": blend}}
    print("Against the submitted bots:")
    field = compare(variants, class_slots(per_cell, 901, 9_000_000), 8)
    show(field)
    print("\nAgainst the stand-in opponents:")
    zoo = compare(variants, make_slots(per_cell // 2, 902, POOL, seed_base=9_500_000), 8)
    show(zoo)
    (ROOT / "results" / "class_tuned_confirm.json").write_text(json.dumps(
        {"by_n": {str(k): v for k, v in new.items()}, "class_field": field, "stand_ins": zoo},
        indent=1) + "\n")


if __name__ == "__main__":
    main()
