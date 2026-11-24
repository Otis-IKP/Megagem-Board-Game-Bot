"""The per-player-count settings the Market Reader had before tuning against
the submitted bots. Kept so the comparison scripts stay reproducible."""

BY_N_V2 = {
    3: {"lam0": 1.978, "kappa": 0.225, "delta": -0.423, "rho": 0.465, "prior_weight": 2.224, "decay": 0.942, "la_mix": 0.054, "win_cost": -1.419, "race_pen": 0.785, "deny_w": 0.204},
    4: {"lam0": 2.276, "kappa": 0.243, "delta": -0.613, "rho": 0.458, "prior_weight": 2.068, "decay": 0.969, "la_mix": 0.136, "win_cost": -0.857, "race_pen": 0.784, "deny_w": 0.167},
    5: {"lam0": 2.75, "kappa": 0.255, "delta": -0.145, "rho": 0.389, "prior_weight": 2.317, "decay": 0.971, "la_mix": 0.039, "win_cost": -0.764, "race_pen": 0.915, "deny_w": 0.202},
}
