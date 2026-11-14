"""Bot 1 - Fair-Value Pacer: bid a fixed share of what each lot is worth."""

from bots import Bot, BotInfo

from .otis_core import View, choose_reveal, clamp_bid


class FairValuePacer(Bot):
    # Tuned by arena/tune.py (see results/tuned_FairValuePacer.json).
    # share: fraction of the adjusted value to bid on gems
    # lam0/lam_min/kappa: coin premium schedule; delta: value shading
    # rho: mission progress credit; inv_share/loan_share: financing bids
    PARAMS = {
        "share": 0.289, "lam0": 0.581, "lam_min": 0.05, "kappa": -0.501, "delta": 2.245,
        "rho": 0.51, "inv_share": 0.16, "loan_share": 0.756, "reveal_sign": 1.0,
    }

    def get_bid(self, info: BotInfo) -> int:
        p = self.PARAMS
        v = View(info)
        lam = v.coin_premium(p["lam0"], p["lam_min"], p["kappa"])
        if v.kind == "treasure":
            value, _ = v.lot_value(p["rho"])
            return clamp_bid(p["share"] * (value - p["delta"]) / (1.0 + lam), v.max_bid)
        if v.kind == "invest":
            limit = v.amount / max(lam, 1e-6)
            return clamp_bid(p["inv_share"] * limit, v.max_bid)
        if v.kind == "loan":
            limit = lam * v.amount / (1.0 + lam)
            return clamp_bid(p["loan_share"] * limit, v.max_bid)
        return 0

    def choose_hidden_gem(self, info: BotInfo, bids) -> int:
        return choose_reveal(info, self.PARAMS["reveal_sign"])
