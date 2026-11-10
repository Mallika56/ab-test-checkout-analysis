"""Statistics for a two-arm conversion experiment, written out explicitly.

Everything here is a small, readable function so each formula can be explained in an
interview. The tests in tests/test_stats.py check them against scipy/statsmodels.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


# --------------------------------------------------------------------- design
def required_sample_size(p_baseline: float, mde_relative: float,
                         alpha: float = 0.05, power: float = 0.80) -> int:
    """Users needed PER ARM to detect a relative lift of `mde_relative` (two-sided)."""
    p1 = p_baseline
    p2 = p_baseline * (1 + mde_relative)
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    p_bar = (p1 + p2) / 2
    n = ((z_a * np.sqrt(2 * p_bar * (1 - p_bar))
          + z_b * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (p2 - p1) ** 2
    return int(np.ceil(n))


def minimum_detectable_effect(p_baseline: float, n_per_arm: int,
                              alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest absolute difference detectable with `n_per_arm` users per arm (approx.)."""
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    return float((z_a + z_b) * np.sqrt(2 * p_baseline * (1 - p_baseline) / n_per_arm))


# --------------------------------------------------------------------- validity
def sample_ratio_mismatch(n_control: int, n_treatment: int,
                          expected_share: float = 0.5) -> dict:
    """Chi-square goodness-of-fit: did randomization split users as designed?

    A tiny p-value (convention: < 0.001) means the split is broken and the experiment
    results can't be trusted, whatever they say.
    """
    total = n_control + n_treatment
    expected = [total * expected_share, total * (1 - expected_share)]
    chi2, p = stats.chisquare([n_control, n_treatment], f_exp=expected)
    return {"n_control": n_control, "n_treatment": n_treatment,
            "control_share": n_control / total, "chi2": float(chi2), "p_value": float(p)}


# --------------------------------------------------------------------- inference
@dataclass
class ProportionTest:
    """Result of a two-proportion z-test: rates, the pooled test statistic, and both CIs."""

    conv_control: int
    n_control: int
    conv_treatment: int
    n_treatment: int
    rate_control: float
    rate_treatment: float
    abs_diff: float
    rel_lift: float
    z: float
    p_value: float
    ci_low: float
    ci_high: float
    rel_ci_low: float
    rel_ci_high: float

    def as_dict(self) -> dict:
        """Return the result's fields as a plain dict with numpy scalars cast to float."""
        return {k: (float(v) if isinstance(v, (np.floating, float)) else v)
                for k, v in self.__dict__.items()}


def two_proportion_test(conv_c: int, n_c: int, conv_t: int, n_t: int,
                        alpha: float = 0.05) -> ProportionTest:
    """Two-sided z-test for treatment rate - control rate.

    * The test statistic uses the POOLED rate (that's the null hypothesis: no difference).
    * The confidence interval uses the UNPOOLED standard error (we no longer assume
      the rates are equal when estimating how big the difference is).
    """
    p_c, p_t = conv_c / n_c, conv_t / n_t
    diff = p_t - p_c
    p_pool = (conv_c + conv_t) / (n_c + n_t)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = diff / se_pool
    p_value = 2 * stats.norm.sf(abs(z))

    se = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    lo, hi = diff - z_crit * se, diff + z_crit * se
    return ProportionTest(conv_c, n_c, conv_t, n_t, p_c, p_t, diff, diff / p_c,
                          float(z), float(p_value), float(lo), float(hi),
                          float(lo / p_c), float(hi / p_c))


def bayesian_comparison(conv_c: int, n_c: int, conv_t: int, n_t: int,
                        draws: int = 400_000, seed: int = 7) -> dict:
    """Beta-Binomial model with a flat Beta(1, 1) prior.

    Returns P(treatment beats control) and the expected loss of shipping each
    variant: how much conversion rate you'd give up, on average, if you picked it and
    it turned out to be the worse one.
    """
    rng = np.random.default_rng(seed)
    c = rng.beta(1 + conv_c, 1 + n_c - conv_c, draws)
    t = rng.beta(1 + conv_t, 1 + n_t - conv_t, draws)
    return {
        "prob_treatment_better": float((t > c).mean()),
        "expected_loss_ship_treatment": float(np.maximum(c - t, 0).mean()),
        "expected_loss_keep_control": float(np.maximum(t - c, 0).mean()),
        "rel_lift_95_credible": [float(x) for x in np.percentile((t - c) / c, [2.5, 97.5])],
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (controls false positives across segments)."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adjusted[idx] = min(running, 1.0)
    return adjusted.tolist()


# --------------------------------------------------------------------- peeking
def peeking_false_positive_rate(p: float, users_per_day_per_arm: int, days: int,
                                sims: int = 2000, alpha: float = 0.05, seed: int = 11) -> dict:
    """Simulate A/A tests (no real difference) and compare two stopping rules:

    * fixed horizon: test once, at the end
    * daily peeking: stop as soon as any daily check shows p < alpha

    The gap between the two is why you pre-register the sample size and don't stop
    the moment a result looks significant.
    """
    rng = np.random.default_rng(seed)
    a = rng.binomial(users_per_day_per_arm, p, size=(sims, days)).cumsum(axis=1)
    b = rng.binomial(users_per_day_per_arm, p, size=(sims, days)).cumsum(axis=1)
    n = users_per_day_per_arm * np.arange(1, days + 1)
    p_pool = (a + b) / (2 * n)
    se = np.sqrt(p_pool * (1 - p_pool) * (2 / n))
    z = (b / n - a / n) / se
    pvals = 2 * stats.norm.sf(np.abs(z))
    return {
        "sims": sims,
        "days": days,
        "fixed_horizon_fpr": float((pvals[:, -1] < alpha).mean()),
        "daily_peeking_fpr": float((pvals < alpha).any(axis=1).mean()),
    }
