"""Compare the second-round tunings with the first tuned Market Reader.

    python -m arena.compare_tuned select    # choose a version (selection deals)
    python -m arena.compare_tuned confirm   # confirm on fresh deals
"""

import json
import sys

from arena import ROOT
from arena.ablate import POOL, compare, make_slots, show
from arena.engine import make_class, spec

from otis_bots.zoo import HOLDOUT_ZOO


def load(name: str) -> dict:
    return json.loads((ROOT / "results" / f"tuned_{name}.json").read_text())["params"]


def variants() -> dict:
    v1 = {k: v for k, v in make_class(spec("MarketReaderV1")).PARAMS.items()}
    off = {"la_mix": 0.0, "color_k": 0.0, "split_lots": 0.0, "censor": 0.0,
           "reset_detect": 0.0, "supply_check": 0.0, "race_pen": 1.0,
           "deny_w": 0.0, "win_cost": 0.0, "by_n": None, "la_share": 0.6}
    base = {**v1, **off}
    full = load("mr_full_all")
    return {
        "first tuned version": base,
        "1: wider ranges, stronger pool": {**base, **load("mr_wide")},
        "1 + kept switches, one setting": {**base, **full},
        "6: separate settings per player count": {
            **base, **full,
            "by_n": {n: load(f"mr_full_n{n}") for n in (3, 4, 5)},
        },
    }


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "select"
    base = 3_000_000 if mode == "select" else 6_000_000
    out = {}
    for label, pool, seed, rotate in (
        ("All opponents incl. strong bots", POOL, 303, False),
        ("Opponents never used in tuning", HOLDOUT_ZOO, 304, False),
        ("All opponents, seats swap mid-series", POOL, 305, True),
    ):
        per_cell = 40 if not rotate else 20
        slots = make_slots(per_cell, seed, pool, rotate, seed_base=base)
        print(f"\n{label} ({len(slots)} series, {mode} deals)")
        out[label] = compare(variants(), slots, 8)
        show(out[label])
    (ROOT / "results" / f"compare_tuned_{mode}.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
