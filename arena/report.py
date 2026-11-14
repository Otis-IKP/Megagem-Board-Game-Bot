"""Print results/evaluation.json as Markdown tables.

    python -m arena.report [results/evaluation.json]
"""

import json
import sys

from arena import ROOT


def table(header, rows):
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join("---" for _ in header) + "|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()


def pct(x):
    return f"{100 * x:.1f}%"


def field(rep, title):
    print(f"### {title}\n")
    ents = rep["entrants"]
    games = next(iter(ents.values()))["games"]
    print(f"{rep['slots']} series, {games} games per bot.\n")
    table(
        ["Bot", "Points per game", "95% range", "Win rate", "Lead over table average"],
        [[e, f"{d['mean_score']:.1f}", f"{d['score_ci'][0]:.1f} to {d['score_ci'][1]:.1f}",
          pct(d["win_rate"]), f"{d['margin_vs_table']:+.1f}"] for e, d in ents.items()],
    )
    table(
        ["Bot"] + [f"{n} players" for n in (3, 4, 5)] + [f"Chart {c}" for c in "ABCDE"],
        [[e] + [f"{d['by_players'][str(n)]['mean_score']:.1f}" for n in (3, 4, 5)]
         + [f"{d['by_chart'][c]['mean_score']:.1f}" for c in "ABCDE"] for e, d in ents.items()],
    )
    table(
        ["Pair", "Points per game difference", "95% range", "Series where first is ahead"],
        [[k, f"{v['mean_diff']:+.2f}", f"{v['ci'][0]:+.2f} to {v['ci'][1]:+.2f}",
          pct(v["share_of_series_ahead"])] for k, v in rep["paired"].items()],
    )
    table(
        ["Bot", "Games 1-3", "Games 4-9", "Games 10-15"],
        [[e, f"{sum(d['by_game_index'][0:3]) / 3:.1f}", f"{sum(d['by_game_index'][3:9]) / 6:.1f}",
          f"{sum(d['by_game_index'][9:15]) / 6:.1f}"] for e, d in ents.items()],
    )


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "results" / "evaluation.json"
    rep = json.load(open(path))
    field(rep["field_all_opponents"], "Field test: all test opponents")
    field(rep["field_unseen_opponents"], "Field test: opponents never used in tuning")
    print("### Head to head: all three at one table\n")
    h = rep["head_to_head"]
    table(
        ["Bot", "Points per game", "95% range", "Win rate", "3 players", "4 players", "5 players"],
        [[c, f"{d['mean_score']:.1f}", f"{d['score_ci'][0]:.1f} to {d['score_ci'][1]:.1f}", pct(d["win_rate"])]
         + [f"{h[n][c]['mean_score']:.1f} / {pct(h[n][c]['win_rate'])}" for n in "345"]
         for c, d in h["all"].items()],
    )
    print("### One bot against copies of another (win rate / lead over table)\n")
    m = rep["one_vs_copies"]
    names = list(m)
    table(["Row vs copies of"] + names,
          [[a] + [f"{pct(m[a][b]['win_rate'])} / {m[a][b]['margin']:+.0f}" for b in names] for a in names])
    for key, value in rep.items():
        if key.startswith("league"):
            print(f"### League table: {key}\n")
            table(["Rank", "Bot", "Points per game", "Win rate", "Games"],
                  [[i + 1, b, f"{d['mean_score']:.1f}", pct(d["win_rate"]), d["games"]]
                   for i, (b, d) in enumerate(value.items())])


if __name__ == "__main__":
    main()
