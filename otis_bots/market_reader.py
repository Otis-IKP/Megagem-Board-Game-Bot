"""Bot 2 - Market Reader: model each opponent's bids, then bid just enough."""

from bots import Bot, BotInfo, RoundResult
from constants import STANDARD_GEMS

from .otis_core import (
    View,
    choose_reveal,
    clamp_bid,
    color_slopes,
    mission_need,
    mission_value,
    public_color_values,
)

# Prior guesses for an opponent with no history, as fractions of the "value"
# scale: lot value for gems, coins held for investments, loan size for loans.
_PRIOR = {
    "treasure": (0.0, 0.15, 0.3, 0.45, 0.6),
    "invest": (0.0, 0.1, 0.25, 0.5),
    "loan": (0.0, 0.1, 0.2, 0.3),
}
_HISTORY_LIMIT = 60
_PRICE_EMA = 0.2


class MarketReader(Bot):
    # Version 2. Core settings (tuned by arena/tune.py, see results/tuned_mr_full_*.json):
    #   lam0/lam_min/kappa  coin premium schedule      delta  value shading
    #   rho  mission progress credit   prior_weight/decay  opponent model
    # Optional parts, each off at the value shown in brackets:
    #   la_mix [0]       share of the coin premium taken from look-ahead
    #   la_share         share of future gems the look-ahead plans to buy
    #   color_k [0]      strength of inferring rivals' hands from their bids
    #   split_lots [0]   model one-gem and two-gem lots separately
    #   censor [0]       treat all-in bids as "at least this much"
    #   reset_detect [0] forget a seat's history when its behaviour changes
    #   supply_check [0] drop missions whose named colours have run out
    #   race_pen [1]     scale mission progress when a rival is closer
    #   deny_w [0]       credit for stopping a rival completing a mission
    #   win_cost [0]     points charged for any win (forced reveal, tie order)
    #   by_n [None]      overrides per player count, e.g. {3: {"lam0": 1.2}}
    PARAMS = {
        # Fallback settings (tuned over 3, 4 and 5 players together).
        "lam0": 2.275, "kappa": 0.143, "delta": -0.675, "rho": 0.454, "prior_weight": 2.348, "decay": 0.955, "la_mix": 0.069, "win_cost": -0.801, "race_pen": 0.911, "deny_w": 0.086,
        "lam_min": 0.05, "reveal_sign": 1.0, "la_share": 6.0, "reset_detect": 1.0,
        "color_k": 0.0, "split_lots": 0.0, "censor": 0.0, "supply_check": 0.0,
        # Settings tuned separately for each player count.
        "by_n": {
            3: {"lam0": 1.978, "kappa": 0.225, "delta": -0.423, "rho": 0.465, "prior_weight": 2.224, "decay": 0.942, "la_mix": 0.054, "win_cost": -1.419, "race_pen": 0.785, "deny_w": 0.204},
            4: {"lam0": 2.276, "kappa": 0.243, "delta": -0.613, "rho": 0.458, "prior_weight": 2.068, "decay": 0.969, "la_mix": 0.136, "win_cost": -0.857, "race_pen": 0.784, "deny_w": 0.167},
            5: {"lam0": 2.75, "kappa": 0.255, "delta": -0.145, "rho": 0.389, "prior_weight": 2.317, "decay": 0.971, "la_mix": 0.039, "win_cost": -0.764, "race_pen": 0.915, "deny_w": 0.202},
        },
    }

    def __init__(self) -> None:
        # history[(opponent id, kind)] = rows of
        # (bid, abs scale, value scale, cap, bid was all-in)
        self.history: dict = {}
        self.pending = None
        self.price = None  # running winning price per gem
        self.color_sig = [0.0] * len(STANDARD_GEMS)

    def on_game_start(self) -> None:
        self.color_sig = [0.0] * len(STANDARD_GEMS)  # hands are new each game
        self.pending = None

    def _params(self, n: int) -> dict:
        p = self.PARAMS
        extra = p.get("by_n")
        if extra:
            override = extra.get(n) or extra.get(str(n))
            if override:
                return {**p, **override}
        return p

    # ------------------------------------------------------- opponent model

    def _scales(self, v: View, info: BotInfo, p: dict) -> dict:
        """Per-opponent (absolute scale, value scale, legal cap) for this lot."""
        out = {}
        public = public_color_values(info) if v.kind == "treasure" else None
        for opp in info.other_players:
            if v.kind == "treasure":
                coll = tuple(opp.won_gems.get(g, 0) for g in STANDARD_GEMS)
                value = sum(public[i] for i in v.lot_idx) + mission_value(
                    v.specs, coll, v.lot_idx, v.gems_left_after, p["rho"]
                )
                out[opp.id] = (float(len(v.lot_idx)), value, opp.coins)
            elif v.kind == "invest":
                out[opp.id] = (1.0, float(opp.coins), opp.coins)
            else:
                out[opp.id] = (1.0, float(v.amount), opp.coins + v.amount)
        return out

    def _samples(self, opp_id: int, kind: str, lot_size: int, p: dict):
        if kind == "treasure" and p["split_lots"]:
            rows = self.history.get((opp_id, f"treasure{lot_size}"))
            if rows and len(rows) >= 4:
                return rows
        return self.history.get((opp_id, kind))

    def _bid_pmf(self, samples, scale, kind: str, p: dict) -> list[float]:
        """Probability of each bid 0..cap for one opponent on the current lot."""
        abs_now, val_now, cap = scale
        pmf = [0.0] * (cap + 1)
        prior = _PRIOR[kind]
        w = p["prior_weight"] / len(prior)
        for r in prior:
            pmf[clamp_bid(r * val_now, cap)] += w
        if samples:
            if p["censor"]:
                free = [s for s in samples if not s[4]]
                if len(free) >= 3:
                    samples = free
            # Pick the scale that explains this opponent's past bids best:
            # fixed amounts, a share of value, or a share of their budget.
            best, best_err = 1, None
            if len(samples) >= 3:
                for h in (0, 1, 2):
                    ratios = sorted(
                        s[0] / s[1 + h] for s in samples if s[1 + h] > 0
                    )
                    if not ratios:
                        continue
                    med = ratios[len(ratios) // 2]
                    err = sum(
                        abs(s[0] - min(s[3], med * s[1 + h])) for s in samples
                    ) / len(samples)
                    if best_err is None or err < best_err - 1e-9:
                        best, best_err = h, err
            now = (abs_now, val_now, float(cap))[best]
            weight = 1.0
            for s in reversed(samples):
                base = s[1 + best]
                guess = s[0] if base <= 0 else s[0] / base * now
                pmf[clamp_bid(guess, cap)] += weight
                weight *= p["decay"]
        total = sum(pmf)
        return [x / total for x in pmf]

    def _win_probs(self, v: View, info: BotInfo, scales: dict, p: dict):
        """P(my bid b wins) for b = 0..max_bid, and each rival's expected bid."""
        me, n, prev = info.self_player.id, info.num_players, info.previous_winner_id
        probs = [1.0] * (v.max_bid + 1)
        expected = {}
        for opp in info.other_players:
            samples = self._samples(opp.id, v.kind, len(v.lot_idx), p)
            pmf = self._bid_pmf(samples, scales[opp.id], v.kind, p)
            expected[opp.id] = sum(b * q for b, q in enumerate(pmf))
            if prev is None:
                tie = 0.5
            else:
                tie = 1.0 if (me - prev - 1) % n < (opp.id - prev - 1) % n else 0.0
            below = 0.0
            for b in range(v.max_bid + 1):
                at = pmf[b] if b < len(pmf) else 0.0
                probs[b] *= below + tie * at
                below += at
        return probs, expected

    # ----------------------------------------------------------- look-ahead

    def _lookahead(self, v: View, info: BotInfo, p: dict):
        """(premium per coin, spare coins, coins short) from what is still to
        come: the gems left, the going price, and what rivals can afford."""
        pool = sum(v.avail)
        if pool <= 0 or v.gems_left_after <= 0:
            return 0.0, float(v.coins), 0.0
        avg_value = sum(v.values[c][0] * v.avail[c] for c in range(len(v.avail))) / pool
        price = self.price if self.price is not None else 0.35 * avg_value
        richest = max(o.coins for o in info.other_players)
        price = max(0.5, min(price, richest + 1.0))
        lam = min(3.0, max(0.0, avg_value / price - 1.0))
        wanted = v.gems_left_after * price * p["la_share"]
        return lam, max(0.0, v.coins - wanted), max(0.0, wanted - v.coins)

    # ------------------------------------------------------------ callbacks

    def get_bid(self, info: BotInfo) -> int:
        v = View(info)
        if v.kind == "none":
            return 0
        p = self._params(v.n)
        if p["color_k"] and v.kind == "treasure":
            slopes = color_slopes(info)
            v.values = [
                (max(0.0, m + p["color_k"] * self.color_sig[c] * slopes[c]), var)
                for c, (m, var) in enumerate(v.values)
            ]
        scales = self._scales(v, info, p)
        probs, expected = self._win_probs(v, info, scales, p)
        self.pending = (info.round_number, v.kind, scales, v.lot_idx, expected)

        lam = v.coin_premium(p["lam0"], p["lam_min"], p["kappa"])
        mix = 0.0 if v.final else p["la_mix"]
        la_lam, spare, short = self._lookahead(v, info, p) if mix else (0.0, 0.0, 0.0)

        def premium(b):  # extra cost of spending or locking b coins
            return (1.0 - mix) * lam * b + mix * la_lam * max(0.0, b - spare)

        if v.kind == "treasure":
            value = v.lot_value(p["rho"], bool(p["supply_check"]), p["race_pen"])[0]
            value -= p["delta"]
            if p["deny_w"] and v.specs:
                after = [list(c) for c in v.opp_colls]
                for coll in after:
                    for i in v.lot_idx:
                        coll[i] += 1
                for spec in v.specs:
                    if any(mission_need(spec, tuple(c)) == 0 for c in after):
                        value += p["deny_w"] * spec[0]
            gain = lambda b: value - b - premium(b)  # noqa: E731
        elif v.kind == "invest":
            gain = lambda b: v.amount - premium(b)  # noqa: E731
        else:
            def gain(b):
                got = max(0.0, v.amount - b)
                return (1.0 - mix) * lam * got + mix * la_lam * min(got, short) - b
        best_bid, best_u = 0, 0.0
        cost = p["win_cost"]
        for b in range(v.max_bid + 1):
            u = (gain(b) - cost) * probs[b]
            if u > best_u + 1e-9:
                best_bid, best_u = b, u
        return clamp_bid(best_bid, v.max_bid)

    def choose_hidden_gem(self, info: BotInfo, bids) -> int:
        return choose_reveal(info, self.PARAMS["reveal_sign"])

    def on_round_end(self, info: BotInfo, result: RoundResult) -> None:
        pending, self.pending = self.pending, None
        if pending is None or pending[0] != info.round_number:
            return
        _, kind, scales, lot_idx, expected = pending
        p = self._params(info.num_players)
        if kind == "treasure" and lot_idx:
            per_gem = result.winning_bid / len(lot_idx)
            self.price = (
                per_gem if self.price is None
                else self.price + _PRICE_EMA * (per_gem - self.price)
            )
        for opp_id, bid in result.bids.items():
            scale = scales.get(opp_id)
            if scale is None:
                continue
            row = (bid, scale[0], scale[1], float(scale[2]), bid >= scale[2] > 0)
            keys = [(opp_id, kind)]
            if kind == "treasure":
                keys.append((opp_id, f"treasure{len(lot_idx)}"))
                # A rival paying over the odds for a colour probably holds it.
                z = (bid - expected.get(opp_id, bid)) / max(2.0, scale[1])
                z = max(-1.0, min(1.0, z)) / (len(scales) * len(lot_idx))
                for c in lot_idx:
                    self.color_sig[c] += z
            for key in keys:
                rows = self.history.setdefault(key, [])
                rows.append(row)
                if len(rows) > _HISTORY_LIMIT:
                    del rows[0]
            if p["reset_detect"]:
                self._maybe_reset(opp_id, kind)

    def _maybe_reset(self, opp_id: int, kind: str) -> None:
        """Drop old history if a seat's recent bids no longer fit it."""
        rows = self.history.get((opp_id, kind))
        if not rows or len(rows) < 12:
            return
        old, recent = rows[:-5], rows[-5:]
        for h in (0, 1):
            ratios = sorted(s[0] / s[1 + h] for s in old if s[1 + h] > 0)
            if not ratios:
                return
            med = ratios[len(ratios) // 2]
            err = lambda group: sum(  # noqa: E731
                abs(s[0] - min(s[3], med * s[1 + h])) for s in group
            ) / len(group)
            if err(recent) <= 3.0 * err(old) + 2.0:
                return
        del rows[:-5]
        for size in (1, 2):
            extra = self.history.get((opp_id, f"{kind}{size}"))
            if extra:
                del extra[:-3]
