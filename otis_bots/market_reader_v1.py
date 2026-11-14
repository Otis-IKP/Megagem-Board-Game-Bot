"""Frozen copy of the first tuned Market Reader, kept as a yardstick."""

from bots import Bot, BotInfo, RoundResult
from constants import STANDARD_GEMS

from .otis_core import (
    View,
    choose_reveal,
    clamp_bid,
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


class MarketReaderV1(Bot):
    # Tuned by arena/tune.py (see results/tuned_MarketReader.json).
    PARAMS = {
        "lam0": 1.837, "lam_min": 0.05, "kappa": -0.109, "delta": 0.0, "rho": 0.356,
        "prior_weight": 2.766, "decay": 0.939, "reveal_sign": 1.0,
    }

    def __init__(self) -> None:
        # history[(opponent id, kind)] = list of (bid, abs scale, value scale, cap)
        self.history: dict = {}
        self.pending = None

    # ------------------------------------------------------- opponent model

    def _scales(self, v: View, info: BotInfo) -> dict:
        """Per-opponent (absolute scale, value scale, legal cap) for this lot."""
        out = {}
        public = public_color_values(info) if v.kind == "treasure" else None
        for opp in info.other_players:
            if v.kind == "treasure":
                coll = tuple(opp.won_gems.get(g, 0) for g in STANDARD_GEMS)
                value = sum(public[i] for i in v.lot_idx) + mission_value(
                    v.specs, coll, v.lot_idx, v.gems_left_after, self.PARAMS["rho"]
                )
                out[opp.id] = (float(len(v.lot_idx)), value, opp.coins)
            elif v.kind == "invest":
                out[opp.id] = (1.0, float(opp.coins), opp.coins)
            else:
                out[opp.id] = (1.0, float(v.amount), opp.coins + v.amount)
        return out

    def _bid_pmf(self, key, scale, kind: str) -> list[float]:
        """Probability of each bid 0..cap for one opponent on the current lot."""
        abs_now, val_now, cap = scale
        p = self.PARAMS
        pmf = [0.0] * (cap + 1)
        prior = _PRIOR[kind]
        w = p["prior_weight"] / len(prior)
        for r in prior:
            pmf[clamp_bid(r * val_now, cap)] += w
        samples = self.history.get(key)
        if samples:
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

    def _win_probs(self, v: View, info: BotInfo, scales: dict) -> list[float]:
        """P(my bid b wins) for b = 0..max_bid, including tie-break order."""
        me, n, prev = info.self_player.id, info.num_players, info.previous_winner_id
        probs = [1.0] * (v.max_bid + 1)
        for opp in info.other_players:
            pmf = self._bid_pmf((opp.id, v.kind), scales[opp.id], v.kind)
            if prev is None:
                tie = 0.5
            else:
                tie = 1.0 if (me - prev - 1) % n < (opp.id - prev - 1) % n else 0.0
            below = 0.0
            for b in range(v.max_bid + 1):
                at = pmf[b] if b < len(pmf) else 0.0
                probs[b] *= below + tie * at
                below += at
        return probs

    # ------------------------------------------------------------ callbacks

    def get_bid(self, info: BotInfo) -> int:
        p = self.PARAMS
        v = View(info)
        if v.kind == "none":
            return 0
        scales = self._scales(v, info)
        self.pending = (info.round_number, v.kind, scales)
        lam = v.coin_premium(p["lam0"], p["lam_min"], p["kappa"])
        probs = self._win_probs(v, info, scales)
        if v.kind == "treasure":
            value = v.lot_value(p["rho"])[0] - p["delta"]
            gain = lambda b: value - (1.0 + lam) * b  # noqa: E731
        elif v.kind == "invest":
            gain = lambda b: v.amount - lam * b  # noqa: E731
        else:
            gain = lambda b: lam * (v.amount - b) - b  # noqa: E731
        best_bid, best_u = 0, 0.0
        for b in range(v.max_bid + 1):
            u = gain(b) * probs[b]
            if u > best_u + 1e-9:
                best_bid, best_u = b, u
        return clamp_bid(best_bid, v.max_bid)

    def choose_hidden_gem(self, info: BotInfo, bids) -> int:
        return choose_reveal(info, self.PARAMS["reveal_sign"])

    def on_round_end(self, info: BotInfo, result: RoundResult) -> None:
        pending, self.pending = self.pending, None
        if pending is None or pending[0] != info.round_number:
            return
        _, kind, scales = pending
        for opp_id, bid in result.bids.items():
            scale = scales.get(opp_id)
            if scale is None:
                continue
            rows = self.history.setdefault((opp_id, kind), [])
            rows.append((bid, scale[0], scale[1], float(scale[2])))
            if len(rows) > _HISTORY_LIMIT:
                del rows[0]
