"""Checks for the bots and the testing ground. Run from the repo root:

    python -m unittest discover -s tests -v      (Python 3.10+)
"""

import itertools
import logging
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from random import Random

import arena  # noqa: F401  (sets sys.path)
from arena.engine import CHARTS, LocalRunner, make_class, run_series, spec
from bot_runner import BotRunner
from constants import STANDARD_GEMS, AuctionType
from decks import MISSION_CARDS
from harness import play_game

from otis_bots.otis_core import hyper_pmf, mission_need, mission_spec

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ["FairValuePacer", "MarketReader", "EvolvedWeights"]


class CoreMathTest(unittest.TestCase):
    def test_pmf_sums_to_one(self):
        for pool, hits, draws in itertools.product(range(0, 26), range(0, 7), range(0, 13)):
            if hits <= pool and draws <= pool:
                self.assertAlmostEqual(sum(hyper_pmf(pool, hits, draws)), 1.0, places=9)

    def test_expected_value_matches_independent_calculation(self):
        # 3 players, chart A, holding k of a colour, nothing else seen.
        chart = CHARTS["A"].values
        expected = {0: 9.60, 1: 11.98, 2: 14.33, 3: 16.59, 4: 18.60, 5: 20.00}
        for k, want in expected.items():
            pmf = hyper_pmf(25, 6 - k, 10)
            got = sum(p * chart[min(6, k + j)] for j, p in enumerate(pmf))
            self.assertAlmostEqual(got, want, places=2)

    def test_mission_need_matches_brute_force(self):
        rng = Random(3)
        colls = [tuple(rng.randint(0, 3) for _ in range(5)) for _ in range(150)]
        colls += [(0,) * 5, (1, 1, 1, 1, 0), (2, 2, 0, 0, 0), (3, 0, 0, 0, 0)]
        adds = [
            combo
            for depth in range(0, 5)
            for combo in itertools.combinations_with_replacement(range(5), depth)
        ]
        for mission in MISSION_CARDS:
            s = mission_spec(mission)
            for coll in colls:
                brute = None
                for combo in adds:  # ordered by size
                    trial = list(coll)
                    for i in combo:
                        trial[i] += 1
                    if mission.is_satisfied(dict(zip(STANDARD_GEMS, trial))):
                        brute = len(combo)
                        break
                self.assertEqual(mission_need(s, coll), brute, (mission, coll))


class CheckedRunner(LocalRunner):
    """Fails the test on any illegal decision and records the slowest call."""

    slowest = 0.0

    def call(self, method, *args):
        start = time.perf_counter()
        result = getattr(self.bot, method)(*args)
        CheckedRunner.slowest = max(CheckedRunner.slowest, time.perf_counter() - start)
        if method == "get_bid":
            info = args[0]
            cap = info.self_player.coins
            if info.current_auction.type is AuctionType.LOAN:
                cap += info.current_auction.value
            assert type(result) is int and 0 <= result <= cap, (self.label, result, cap)
        if method == "choose_hidden_gem":
            hand = args[0].self_player.hidden_gems
            assert type(result) is int and 0 <= result < len(hand), (self.label, result)
        return result if type(result) is int else None


class LegalityTest(unittest.TestCase):
    def test_every_decision_is_legal_and_fast(self):
        rng = Random(11)
        pool = CANDIDATES + ["RandomBot", "AggressiveBot", "ZeroBot", "HalfBudgetBot"]
        games = 0
        for n in (3, 4, 5):
            for chart in "ABCDE":
                for _ in range(6):
                    names = [rng.choice(CANDIDATES)] + rng.choices(pool, k=n - 1)
                    runners = [CheckedRunner(make_class(spec(x))) for x in names]
                    random.seed(games)
                    for seed in range(3):
                        play_game(n, value_chart=CHARTS[chart], rng=Random(1000 * games + seed), bots=runners)
                        games += 1
        self.assertLess(CheckedRunner.slowest, 0.25, "a decision took too long")


class HarnessFidelityTest(unittest.TestCase):
    def test_in_process_matches_the_real_isolated_harness(self):
        # Deterministic bots only: random ones draw different numbers per process.
        names = ["FairValuePacer", "MarketReader", "EvolvedWeights", "MarketReader", "FairValuePacer"]
        seeds = [5, 6, 7, 8, 9, 10]
        for n, chart in ((3, "A"), (4, "E"), (5, "C")):
            fast = run_series({"specs": [spec(x) for x in names[:n]], "chart": chart, "seeds": seeds})
            runners = [BotRunner(make_class(spec(x)), timeout=1.0, seed=1) for x in names[:n]]
            try:
                with self.assertNoLogs("bot_runner", level=logging.WARNING):
                    real = [
                        list(play_game(n, value_chart=CHARTS[chart], rng=Random(s), bots=runners).scores)
                        for s in seeds
                    ]
            finally:
                for r in runners:
                    r.close()
            self.assertEqual(fast["scores"], real)


class SwitchesOffTest(unittest.TestCase):
    def test_default_market_reader_equals_frozen_v1_when_switches_are_off(self):
        off = {"la_mix": 0.0, "color_k": 0.0, "split_lots": 0.0, "censor": 0.0,
               "reset_detect": 0.0, "supply_check": 0.0, "race_pen": 1.0,
               "deny_w": 0.0, "win_cost": 0.0, "by_n": None}
        v1 = make_class(spec("MarketReaderV1")).PARAMS
        for n, chart in ((3, "A"), (4, "D"), (5, "E")):
            names = ["HeuristicBot", "ThirdValueBot", "AlgoGemBot", "NaiveChartBot"][: n - 1]
            jobs = [
                {"specs": [s] + [spec(x) for x in names], "chart": chart, "seeds": list(range(40, 52))}
                for s in (spec("MarketReader", {**v1, **off}), spec("MarketReaderV1"))
            ]
            a, b = (run_series(j)["scores"] for j in jobs)
            self.assertEqual(a, b)


class ExportTest(unittest.TestCase):
    def test_export_runs_in_a_copy_of_the_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            fork = Path(tmp) / "fork"
            shutil.copytree(ROOT / "harness", fork, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            for _ in range(2):  # running twice must be harmless
                subprocess.run([sys.executable, str(ROOT / "scripts" / "export_to_fork.py"), str(fork)], check=True, capture_output=True)
            registry = (fork / "src" / "custom_bots.py").read_text()
            self.assertEqual(registry.count("import MarketReader"), 1)
            done = subprocess.run(
                [sys.executable, "src/harness.py", "3", "--seed", "4", "--bots",
                 "custom_bots:MarketReader", "custom_bots:FairValuePacer", "custom_bots:EvolvedWeights"],
                cwd=fork, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("wins with", done.stdout)
            self.assertNotIn("Error", done.stderr)
            self.assertNotIn("Timeout", done.stderr)


if __name__ == "__main__":
    unittest.main()
