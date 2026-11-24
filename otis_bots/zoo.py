"""Test opponents: stand-ins for the kinds of bots other entrants may submit."""

import random

from bots import Bot, BotInfo
from constants import AuctionType

from .otis_core import View, clamp_bid


def _kind(info):
    card = info.current_auction
    if card.type is AuctionType.AUCTION:
        return "treasure", min(card.value, len(info.auction_gems))
    return ("invest" if card.type is AuctionType.INVEST else "loan"), card.value


class ZeroBot(Bot):
    """The harness default: always bids nothing."""


class OneBot(Bot):
    """The harness example: always bids one coin."""

    def get_bid(self, info: BotInfo) -> int:
        return min(1, info.self_player.coins)


class RandomBot(Bot):
    """Bids a uniformly random legal amount."""

    def get_bid(self, info: BotInfo) -> int:
        return random.randint(0, info.self_player.coins)


class OnePerGemBot(Bot):
    """One coin per gem on offer, one coin on loans and investments.

    My own stand-in for the intent described in a classmate's public fork
    (seen 13 Nov 2026, not yet submitted). Their file is not copied here.
    """

    def get_bid(self, info: BotInfo) -> int:
        kind, amount = _kind(info)
        return min(amount if kind == "treasure" else 1, info.self_player.coins)


class AlgoGemBot(Bot):
    """Fixed thresholds, after a public Jane Street programme bot."""

    def get_bid(self, info: BotInfo) -> int:
        kind, amount = _kind(info)
        coins = info.self_player.coins
        if kind == "treasure":
            return min(4 * amount, coins)
        if kind == "loan":
            return min(3 if amount <= 10 else 6, coins + amount)
        return min(3 if amount <= 5 else 6, coins)


class HalfBudgetBot(Bot):
    """Bids half its coins on every gem auction and skips the rest."""

    def get_bid(self, info: BotInfo) -> int:
        kind, _ = _kind(info)
        return info.self_player.coins // 2 if kind == "treasure" else 0


class NaiveChartBot(Bot):
    """Values gems by the display as it stands now, and bids 75% of that."""

    def get_bid(self, info: BotInfo) -> int:
        kind, amount = _kind(info)
        coins = info.self_player.coins
        if kind == "treasure":
            chart = info.value_chart
            value = sum(
                chart.get_value(min(6, info.value_display.get(g, 0)))
                for g in info.auction_gems[:amount]
            )
            return clamp_bid(0.75 * value, coins)
        return min(2, coins) if kind == "invest" else 0


class _ValueShareBot(Bot):
    """Bids a fixed share of the lot's true expected value."""

    SHARE = 0.75
    BASE = 0.0
    INVEST = 0.1  # share of coins bid on investments
    LOAN = 0.0  # share of the loan bid on loans
    LOAN_ONLY_WHEN_POOR = False

    def get_bid(self, info: BotInfo) -> int:
        v = View(info)
        if v.kind == "treasure":
            return clamp_bid(self.BASE + self.SHARE * v.lot_value(0.0)[0], v.max_bid)
        if v.kind == "invest":
            return clamp_bid(self.INVEST * v.coins, v.max_bid)
        if self.LOAN_ONLY_WHEN_POOR and v.coins >= 5:
            return 0
        return clamp_bid(self.LOAN * v.amount, v.max_bid)


class HeuristicBot(_ValueShareBot):
    """75% of expected value; token investment bids; borrows only when broke."""

    SHARE, INVEST, LOAN, LOAN_ONLY_WHEN_POOR = 0.75, 0.12, 0.2, True


class ThirdValueBot(_ValueShareBot):
    """About a third of expected value, like the tuned community bots."""

    SHARE, BASE, INVEST, LOAN = 0.33, 1.0, 0.3, 0.15


class AggressiveBot(_ValueShareBot):
    """Pays close to full value and bids hard on financing."""

    SHARE, INVEST, LOAN = 0.9, 0.5, 0.3


class InvestorBot(_ValueShareBot):
    """Moderate on gems, all-in on investments."""

    SHARE, INVEST, LOAN = 0.5, 1.0, 0.0


class CollectorBot(Bot):
    """Chases missions: pays up for gems that complete one, little otherwise."""

    def get_bid(self, info: BotInfo) -> int:
        v = View(info)
        if v.kind != "treasure":
            return clamp_bid(0.2 * v.coins, v.max_bid) if v.kind == "invest" else 0
        gems, _ = v.lot_value(0.0)
        with_missions, _ = v.lot_value(0.6)
        return clamp_bid(0.4 * gems + 0.9 * (with_missions - gems), v.max_bid)


# Opponents used while tuning, and ones held back to test generalisation.
TRAIN_ZOO = (
    "ZeroBot", "OneBot", "RandomBot", "NaiveChartBot", "HeuristicBot",
    "ThirdValueBot", "InvestorBot",
)
HOLDOUT_ZOO = ("AlgoGemBot", "HalfBudgetBot", "AggressiveBot", "CollectorBot")
ALL_ZOO = TRAIN_ZOO + HOLDOUT_ZOO
# Classmates' submitted bots (pull requests on the course harness as of
# 23 Nov 2026). scripts/fetch_submissions.py copies their files into the
# uncommitted harness/ folder; none of their code is in this repo.
CLASS_BOTS: tuple = (
    "bot_definitions.valuation_bot:ValuationBot",  # PR 1
    "bot_definitions.adaptive_bot:AdaptiveBot",  # PR 2
    "bot_definitions.aggressive_bot:AggressiveBot",  # PR 2
    "bot_definitions.value_liquidity_bot:ValueLiquidityBot",  # PR 2
    "bot_definitions.yale_bot:YaleBot",  # PR 4
    "bot_definitions.adaptive_finance_bots:ConservativeAdaptiveBot",  # PR 5
    "bot_definitions.adaptive_finance_bots:LoanAwareAdaptiveBot",  # PR 5
    "bot_definitions.adaptive_finance_bots:FinanceAwareAdaptiveBot",  # PR 5
    "bot_definitions.ultimate_bot:UltimateBot",  # PR 6
)
# PR 1's SamplingBot needs PR 1's edited harness.py and takes ~6 s per game,
# so it is tested separately on a small sample.
SLOW_CLASS_BOTS: tuple = ("bot_definitions.sampling_bot:SamplingBot",)
