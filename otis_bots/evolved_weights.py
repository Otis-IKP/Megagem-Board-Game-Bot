"""Bot 3 - Evolved Weights: weighted-sum bidding formulas tuned by search."""

from bots import Bot, BotInfo, RoundResult

from .otis_core import View, choose_reveal, clamp_bid

_EMA = 0.3  # how fast the "recent opponent prices" signal updates


class EvolvedWeights(Bot):
    # Gems:        bid = value*(w0 + w1*progress + w2*my + w3*avg + w4*top)
    #                    + w5*std + w6*signal + w7
    # Investments: bid = coins*(a0 + a1*progress + a2*bonus/10 + a3*top)
    #                    + a4*signal + a5
    # Loans:       bid = loan*(c0 + c1*progress + c2*poor + c3*avg)
    #                    + c4*signal + c5
    # my/avg/top are coin counts divided by the starting coins.
    # Tuned by arena/tune.py (see results/tuned_EvolvedWeights.json).
    PARAMS = {
        "w": (
            0.023, 0.124, 0.06, 0.23, 0.072, 0.133, 0.404, -1.08,
            -0.57, 0.845, 0.158, 0.147, 0.511, 0.365,
            0.314, 0.016, 0.014, -0.068, 0.129, -0.075,
        ),
        "rho": 0.316, "reveal_sign": 0.0,
    }

    def __init__(self) -> None:
        # Running gap between the top opponent bid and my no-signal bid.
        self.signal = {"treasure": 0.0, "invest": 0.0, "loan": 0.0}
        self.pending = None

    def _raw_bid(self, v: View, info: BotInfo, signal: float) -> float:
        w = self.PARAMS["w"]
        start = v.start_coins
        opp = [p.coins / start for p in info.other_players]
        my, avg, top = v.coins / start, sum(opp) / len(opp), max(opp)
        progress = 1.0 - v.frac_left
        if v.kind == "treasure":
            value, std = v.lot_value(self.PARAMS["rho"])
            return (
                value * (w[0] + w[1] * progress + w[2] * my + w[3] * avg + w[4] * top)
                + w[5] * std + w[6] * signal + w[7]
            )
        if v.kind == "invest":
            return (
                v.coins * (w[8] + w[9] * progress + w[10] * v.amount / 10 + w[11] * top)
                + w[12] * signal + w[13]
            )
        poor = 1.0 - min(1.0, my)
        return (
            v.amount * (w[14] + w[15] * progress + w[16] * poor + w[17] * avg)
            + w[18] * signal + w[19]
        )

    def get_bid(self, info: BotInfo) -> int:
        v = View(info)
        if v.kind == "none":
            return 0
        baseline = self._raw_bid(v, info, 0.0)
        self.pending = (info.round_number, v.kind, baseline)
        return clamp_bid(self._raw_bid(v, info, self.signal[v.kind]), v.max_bid)

    def choose_hidden_gem(self, info: BotInfo, bids) -> int:
        return choose_reveal(info, self.PARAMS["reveal_sign"])

    def on_round_end(self, info: BotInfo, result: RoundResult) -> None:
        pending, self.pending = self.pending, None
        if pending is None or pending[0] != info.round_number:
            return
        _, kind, baseline = pending
        me = info.self_player.id
        top = max((b for pid, b in result.bids.items() if pid != me), default=0)
        self.signal[kind] += _EMA * ((top - baseline) - self.signal[kind])
