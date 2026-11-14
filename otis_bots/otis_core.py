"""Shared Megagem logic: gem-value beliefs, mission value, coin pricing, reveals.

Standard library only. Imports the harness modules by their top-level names, so
this file works unchanged inside the harness's ``src/bot_definitions`` package.
"""

from functools import lru_cache
from math import comb, sqrt

from constants import (
    CARDS_PER_PLAYER,
    COINS_PER_PLAYER,
    STANDARD_GEMS,
    AuctionType,
    GemType,
    WildCardRequirement,
)

NUM_COLORS = len(STANDARD_GEMS)
_WILD_KIND = {
    None: 0,
    WildCardRequirement.SAME: 1,
    WildCardRequirement.DIFFERENT: 2,
    WildCardRequirement.PAIRS: 3,
}


# ---------------------------------------------------------------- gem values


@lru_cache(maxsize=4096)
def hyper_pmf(pool: int, hits: int, draws: int) -> tuple[float, ...]:
    """P(j of `hits` marked cards land in `draws` cards drawn from `pool`)."""
    if pool <= 0 or draws <= 0 or hits <= 0:
        return (1.0,)
    draws = min(draws, pool)
    hits = min(hits, pool)
    total = comb(pool, draws)
    return tuple(
        comb(hits, j) * comb(pool - hits, draws - j) / total
        for j in range(0, min(hits, draws) + 1)
    )


def _value_stats(chart: tuple[int, ...], base: int, pmf: tuple[float, ...]):
    top = len(chart) - 1
    mean = 0.0
    second = 0.0
    for j, p in enumerate(pmf):
        v = chart[min(base + j, top)]
        mean += p * v
        second += p * v * v
    return mean, max(0.0, second - mean * mean)


def color_values(info) -> list[tuple[float, float]]:
    """(expected final value, variance) per colour, using this bot's own hand."""
    chart = info.value_chart.values
    hidden = info.self_player.hidden_gems
    opp_hidden = sum(p.hidden_gem_count for p in info.other_players)
    unknown = [info.unknown_gems.get(g, 0) for g in STANDARD_GEMS]
    pool = sum(unknown)
    out = []
    for i, gem in enumerate(STANDARD_GEMS):
        base = info.value_display.get(gem, 0) + hidden.count(gem)
        out.append(_value_stats(chart, base, hyper_pmf(pool, unknown[i], opp_hidden)))
    return out


def color_slopes(info) -> list[float]:
    """Change in a colour's expected value if one more of it were in hands."""
    chart = info.value_chart.values
    hidden = info.self_player.hidden_gems
    opp_hidden = sum(p.hidden_gem_count for p in info.other_players)
    unknown = [info.unknown_gems.get(g, 0) for g in STANDARD_GEMS]
    pool = sum(unknown)
    out = []
    for i, gem in enumerate(STANDARD_GEMS):
        base = info.value_display.get(gem, 0) + hidden.count(gem)
        pmf = hyper_pmf(pool, unknown[i], opp_hidden)
        out.append(
            _value_stats(chart, base + 1, pmf)[0] - _value_stats(chart, base, pmf)[0]
        )
    return out


def public_color_values(info, extra_display=None) -> list[float]:
    """Expected final value per colour as seen by someone with no private hand.

    ``extra_display`` is an optional colour index treated as already revealed
    from this bot's hand (used to score reveal choices).
    """
    chart = info.value_chart.values
    hidden = info.self_player.hidden_gems
    all_hidden = sum(p.hidden_gem_count for p in info.other_players) + len(hidden)
    out = []
    unknown = [
        info.unknown_gems.get(g, 0) + hidden.count(g) for g in STANDARD_GEMS
    ]
    display = [info.value_display.get(g, 0) for g in STANDARD_GEMS]
    if extra_display is not None:
        unknown[extra_display] -= 1
        display[extra_display] += 1
        all_hidden -= 1
    pool = sum(unknown)
    for i in range(NUM_COLORS):
        out.append(
            _value_stats(chart, display[i], hyper_pmf(pool, unknown[i], all_hidden))[0]
        )
    return out


# ------------------------------------------------------------------ missions


def mission_spec(mission) -> tuple:
    req = mission.gem_requirements
    return (
        mission.value,
        tuple(req.get(g, 0) for g in STANDARD_GEMS),
        req.get(GemType.WILD_CARD, 0),
        _WILD_KIND[mission.wild_card_requirement],
    )


@lru_cache(maxsize=200_000)
def mission_need(spec: tuple, coll: tuple[int, ...]) -> int:
    """Fewest extra gems that would complete the mission from ``coll``."""
    _, fixed, wild, kind = spec
    need = 0
    rest = []
    for have, want in zip(coll, fixed):
        if have < want:
            need += want - have
            rest.append(0)
        else:
            rest.append(have - want)
    if wild <= 0:
        return need
    if kind == 0:  # any colours
        return need + max(0, wild - sum(rest))
    if kind == 1:  # all the same colour
        return need + max(0, wild - max(rest))
    if kind == 2:  # all different colours
        return need + max(0, wild - sum(1 for r in rest if r > 0))
    pairs_needed = wild // 2 - sum(r // 2 for r in rest)
    if pairs_needed <= 0:
        return need
    odd = sum(r % 2 for r in rest)
    cheap = min(odd, pairs_needed)
    return need + cheap + 2 * (pairs_needed - cheap)


def _mission_weight(spec, coll, gems_left, rho, avail, opp_need, race_pen):
    need = mission_need(spec, coll)
    if need == 0:
        return 1.0
    if need > gems_left:
        return 0.0
    if avail is not None:
        for have, want, supply in zip(coll, spec[1], avail):
            if want - have > supply:
                return 0.0
    weight = rho**need
    if opp_need is not None and opp_need < need:
        weight *= race_pen
    return weight


def mission_value(
    specs, coll, lot_idx, gems_left_after: int, rho: float,
    avail=None, opp_needs=None, race_pen: float = 1.0,
) -> float:
    """Points gained on missions by adding the lot to a collection.

    A completed mission counts in full. Progress short of completion is worth
    ``rho ** gems_still_needed`` of the reward while enough gems remain.
    ``avail`` (unseen supply per colour after this lot) zeroes missions whose
    named colours have run out. ``opp_needs`` (fewest gems any rival needs, per
    mission) scales progress by ``race_pen`` when a rival is closer.
    """
    if not specs:
        return 0.0
    after = list(coll)
    for i in lot_idx:
        after[i] += 1
    after_t = tuple(after)
    coll_t = tuple(coll)
    avail_before = None
    if avail is not None:
        avail_before = list(avail)
        for i in lot_idx:
            avail_before[i] += 1
    total = 0.0
    for k, spec in enumerate(specs):
        rival = opp_needs[k] if opp_needs is not None else None
        w1 = _mission_weight(spec, after_t, gems_left_after, rho, avail, rival, race_pen)
        w0 = _mission_weight(
            spec, coll_t, gems_left_after + len(lot_idx), rho, avail_before, rival,
            race_pen,
        )
        if w1 > w0:
            total += spec[0] * (w1 - w0)
    return total


# ------------------------------------------------------------- auction facts


class View:
    """Everything a bid decision needs, computed once per callback."""

    __slots__ = (
        "info", "card", "kind", "amount", "coins", "max_bid", "n", "start_coins",
        "lot_idx", "frac_left", "final", "values", "specs", "my_coll",
        "gems_left_after", "avail", "opp_colls",
    )

    def __init__(self, info):
        self.info = info
        card = info.current_auction
        self.card = card
        me = info.self_player
        self.coins = me.coins
        self.n = info.num_players
        self.start_coins = COINS_PER_PLAYER[self.n]
        total_auctioned = 30 - self.n * CARDS_PER_PLAYER[self.n]
        self.lot_idx = ()
        self.amount = card.value if card is not None else 0
        if card is None:
            self.kind = "none"
        elif card.type is AuctionType.AUCTION:
            self.kind = "treasure"
            lot = info.auction_gems[: min(card.value, len(info.auction_gems))]
            self.lot_idx = tuple(STANDARD_GEMS.index(g) for g in lot)
        elif card.type is AuctionType.INVEST:
            self.kind = "invest"
        else:
            self.kind = "loan"
        self.max_bid = self.coins + (self.amount if self.kind == "loan" else 0)
        self.gems_left_after = info.gems_remaining - len(self.lot_idx)
        self.frac_left = max(0.0, self.gems_left_after / total_auctioned)
        self.final = self.kind == "treasure" and self.gems_left_after <= 0
        self.values = color_values(info)
        self.specs = tuple(mission_spec(m) for m in info.available_missions)
        self.my_coll = tuple(me.won_gems.get(g, 0) for g in STANDARD_GEMS)
        row_rest = info.auction_gems[len(self.lot_idx):]
        self.avail = [
            info.unknown_gems.get(g, 0) + row_rest.count(g) for g in STANDARD_GEMS
        ]
        self.opp_colls = [
            tuple(p.won_gems.get(g, 0) for g in STANDARD_GEMS)
            for p in info.other_players
        ]

    def opp_needs(self) -> list[int]:
        """Fewest gems any rival still needs, for each open mission."""
        return [
            min(mission_need(spec, coll) for coll in self.opp_colls)
            for spec in self.specs
        ]

    def lot_value(
        self, rho: float, supply_check: bool = False, race_pen: float = 1.0
    ) -> tuple[float, float]:
        """(expected points, standard deviation) of winning the lot for me."""
        mean = sum(self.values[i][0] for i in self.lot_idx)
        var = sum(self.values[i][1] for i in self.lot_idx)
        mean += mission_value(
            self.specs, self.my_coll, self.lot_idx, self.gems_left_after, rho,
            avail=self.avail if supply_check else None,
            opp_needs=self.opp_needs() if race_pen != 1.0 and self.specs else None,
            race_pen=race_pen,
        )
        return mean, sqrt(var)

    def coin_premium(self, lam0: float, lam_min: float, kappa: float) -> float:
        """Extra worth of a spendable coin above its one point of face value."""
        if self.final:
            return 0.0
        spend = 1.0 - min(1.0, self.coins / self.start_coins)
        lam = lam0 * self.frac_left + kappa * (spend - (1.0 - self.frac_left))
        return min(2.5, max(lam_min, lam))


def clamp_bid(x: float, cap: int) -> int:
    """A legal whole-number bid. The harness turns anything else into zero."""
    if x != x:  # NaN
        return 0
    return int(max(0, min(cap, round(x))))


# -------------------------------------------------------------------- reveal


def choose_reveal(info, sign: float = 1.0) -> int:
    """Index of the hidden gem to reveal.

    Every hidden gem reaches the display by the end, so the choice only changes
    what opponents believe meanwhile. With ``sign`` = 1 this reveals the colour
    that least raises rivals' valuations of gems still to be sold.
    """
    hidden = info.self_player.hidden_gems
    if len(hidden) <= 1 or sign == 0.0:
        return 0
    before = public_color_values(info)
    unknown = [info.unknown_gems.get(g, 0) for g in STANDARD_GEMS]
    pool = sum(unknown)
    deck_share = info.gem_deck_count / pool if pool else 0.0
    best_index, best_score = 0, None
    seen = set()
    for index, gem in enumerate(hidden):
        c = STANDARD_GEMS.index(gem)
        if c in seen:
            continue
        seen.add(c)
        after = public_color_values(info, extra_display=c)
        supply = info.auction_gems.count(gem) + unknown[c] * deck_share
        score = -sign * (after[c] - before[c]) * supply
        if best_score is None or score > best_score + 1e-12:
            best_index, best_score = index, score
    return best_index
