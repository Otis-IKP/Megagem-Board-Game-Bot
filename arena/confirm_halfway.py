"""Second fresh-deal check of the half-way settings (current vs class-tuned average).

    python -m arena.confirm_halfway [series per cell]
"""

import json
import sys

from arena import ROOT
from arena.ablate import compare, show
from arena.confirm_class import KEYS, class_slots, tuned_by_n

from otis_bots.market_reader_v2_base import BY_N_V2


def main() -> None:
    per_cell = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    new = tuned_by_n()
    blend = {n: {k: round((new[n][k] + BY_N_V2[n][k]) / 2, 3) for k in KEYS} for n in new}
    r = compare({"current": {"by_n": BY_N_V2}, "half-way": {"by_n": blend}},
                class_slots(per_cell, 903, 9_800_000), 8)
    show(r)
    print(json.dumps(blend))
    (ROOT / "results" / "class_halfway_confirm.json").write_text(json.dumps(
        {"by_n": {str(k): v for k, v in blend.items()}, "class_field": r}, indent=1) + "\n")


if __name__ == "__main__":
    main()
