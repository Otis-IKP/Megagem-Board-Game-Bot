"""Run Megagem games on the real harness engine, in-process for speed.

`LocalRunner` stands in for the harness's `BotRunner` and calls the bot object
directly, so rules, tie-breaks and scoring are the harness's own code. Bot
errors are raised, not swallowed, so bugs surface during testing.
"""

import multiprocessing
import random
from importlib import import_module
from random import Random

from bot_runner import BotRunner
from decks import VALUE_CHARTS
from harness import play_game

CHARTS = {chart.name: chart for chart in VALUE_CHARTS}
BOT_MODULES = {
    "FairValuePacer": "otis_bots.fair_value_pacer",
    "MarketReader": "otis_bots.market_reader",
    "EvolvedWeights": "otis_bots.evolved_weights",
    "MarketReaderV1": "otis_bots.market_reader_v1",
}


def spec(name: str, params: dict | None = None, label: str | None = None) -> tuple:
    """A picklable description of a bot: (module, class, overrides, label)."""
    if ":" in name:  # e.g. "bot_definitions.their_bot:TheirBot" (a submission)
        module, name = name.split(":")
        return (module, name, params, label or name)
    module = BOT_MODULES.get(name, "otis_bots.zoo")
    return (module, name, params, label or name)


def make_class(bot_spec: tuple):
    module, name, params, _ = bot_spec
    cls = getattr(import_module(module), name)
    if params:
        merged = {**cls.PARAMS, **params}
        cls = type(name, (cls,), {"PARAMS": merged, "__module__": module})
    return cls


class LocalRunner(BotRunner):
    def __init__(self, bot_class) -> None:
        self.bot_class = bot_class
        self.timeout = None
        self.seed = None
        self.label = bot_class.__name__
        self.last_error = None
        self._checkpoint = None
        self._process = None
        self._channel = None
        self.bot = bot_class()
        self.bot.timeout_seconds = None

    def call(self, method: str, *args: object):
        result = getattr(self.bot, method)(*args)
        return result if type(result) is int else None

    def close(self) -> None:
        pass


def run_series(job: dict) -> dict:
    """Play several games with one fixed seating; bots keep their memory.

    job: {"specs": [...], "chart": "A", "seeds": [...], "tag": anything}
    Optional "rotate_at" (game index) and "keep" (seat): from that game on the
    other seats swap places, keeping their memory, to mimic a reseating.
    Returns the job plus "scores" (one list per game) and "winners".
    """
    specs = job["specs"]
    random.seed(job["seeds"][0] * 7919 + 13)
    runners = [LocalRunner(make_class(s)) for s in specs]
    scores, winners = [], []
    for index, seed in enumerate(job["seeds"]):
        if index == job.get("rotate_at"):
            keep = job["keep"]
            others = [r for i, r in enumerate(runners) if i != keep]
            others = others[1:] + others[:1]
            runners = others[:keep] + [runners[keep]] + others[keep:]
        result = play_game(
            len(runners), value_chart=CHARTS[job["chart"]], rng=Random(seed),
            bots=runners,
        )
        scores.append(list(result.scores))
        winners.append(list(result.winner_ids))
    return {**job, "scores": scores, "winners": winners}


def run_jobs(jobs: list, workers: int = 8, func=run_series) -> list:
    if workers <= 1 or len(jobs) <= 1:
        return [func(j) for j in jobs]
    ctx = multiprocessing.get_context("spawn")
    chunk = max(1, len(jobs) // (workers * 8))
    with ctx.Pool(workers) as pool:
        return pool.map(func, jobs, chunksize=chunk)
