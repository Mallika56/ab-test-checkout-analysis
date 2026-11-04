"""Check the hand-written statistics against statsmodels / scipy reference implementations."""

import numpy as np
import pytest
from scipy import stats as sps
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (
    confint_proportions_2indep, proportion_effectsize, proportions_ztest,
)

from abtest import stats


def test_z_test_matches_statsmodels():
    r = stats.two_proportion_test(17220, 143293, 17025, 143397)
    z, p = proportions_ztest([17025, 17220], [143397, 143293])
    assert r.z == pytest.approx(z, rel=1e-9)
    assert r.p_value == pytest.approx(p, rel=1e-9)


def test_confidence_interval_matches_statsmodels_wald():
    r = stats.two_proportion_test(17220, 143293, 17025, 143397)
    lo, hi = confint_proportions_2indep(17025, 143397, 17220, 143293, method="wald")
    assert (r.ci_low, r.ci_high) == pytest.approx((lo, hi), rel=1e-9)


def test_relative_lift_is_difference_over_control():
    r = stats.two_proportion_test(100, 1000, 110, 1000)
    assert r.abs_diff == pytest.approx(0.01)
    assert r.rel_lift == pytest.approx(0.10)


def test_srm_detects_broken_split_and_passes_fair_split():
    assert stats.sample_ratio_mismatch(50_000, 50_100)["p_value"] > 0.5
    assert stats.sample_ratio_mismatch(50_000, 52_000)["p_value"] < 0.001


def test_sample_size_close_to_statsmodels_power():
    p0, lift = 0.12, 0.05
    ours = stats.required_sample_size(p0, lift)
    h = proportion_effectsize(p0 * (1 + lift), p0)
    ref = NormalIndPower().solve_power(effect_size=h, alpha=0.05, power=0.8, ratio=1)
    assert ours == pytest.approx(ref, rel=0.01)   # different approximations agree within 1%


def test_mde_and_sample_size_are_consistent():
    p0 = 0.12
    n = stats.required_sample_size(p0, 0.03)
    mde = stats.minimum_detectable_effect(p0, n)
    assert mde / p0 == pytest.approx(0.03, rel=0.05)


def test_holm_adjustment_matches_known_values():
    # classic textbook example
    assert stats.holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_bayesian_probability_symmetric_when_arms_equal():
    b = stats.bayesian_comparison(1200, 10_000, 1200, 10_000, draws=200_000)
    assert b["prob_treatment_better"] == pytest.approx(0.5, abs=0.01)


def test_peeking_inflates_false_positives():
    r = stats.peeking_false_positive_rate(0.12, 2000, 15, sims=800)
    assert r["fixed_horizon_fpr"] == pytest.approx(0.05, abs=0.025)
    assert r["daily_peeking_fpr"] > 2 * r["fixed_horizon_fpr"]
