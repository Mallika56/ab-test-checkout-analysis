"""Run the full experiment readout.

    python scripts/run_analysis.py

Order matches how an analyst should work: integrity -> validity (SRM) -> design (power)
-> primary result -> robustness (sensitivity, Bayesian, time, segments) -> decision.
Writes docs/results/readout.json, CSVs, and docs/img/*.png. Every number in the README
and the decision memo comes from here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402

from abtest import data, stats  # noqa: E402

RES, IMG = ROOT / "docs/results", ROOT / "docs/img"
RES.mkdir(parents=True, exist_ok=True)
IMG.mkdir(parents=True, exist_ok=True)
out: dict = {}

# ---------------------------------------------------------------- 1. integrity
raw = data.load_raw()
out["integrity"] = data.integrity_report(raw).as_dict()

# SQL cross-check: the same counts computed independently in DuckDB
con = duckdb.connect()
con.execute(f"CREATE VIEW ab AS SELECT * FROM read_csv_auto('{ROOT / 'data/raw/ab_data.csv'}')")
con.execute(f"CREATE VIEW countries AS SELECT * FROM read_csv_auto('{ROOT / 'data/raw/countries.csv'}')")
sql = {f.stem: f.read_text() for f in sorted((ROOT / "sql").glob("*.sql"))}
checks = [s for s in sql["01_integrity_checks"].split(";") if "SELECT" in s]
pages = con.execute(checks[0]).df()
dups = con.execute(checks[1]).df()
mis_sql = int(pages.loc[((pages.group == "control") & (pages.landing_page == "new_page"))
                        | ((pages.group == "treatment") & (pages.landing_page == "old_page")), "rows"].sum())
assert mis_sql == out["integrity"]["misaligned_rows"], "SQL and pandas disagree on misaligned rows"
assert int(dups.duplicate_users[0]) == out["integrity"]["duplicate_users"]
assert int(dups.users_in_both_groups[0]) == out["integrity"]["users_in_both_groups"]
daily_sql = con.execute(sql["02_daily_conversion"]).df()
country_sql = con.execute(sql["03_conversion_by_country"]).df()
daily_sql.to_csv(RES / "daily_conversion.csv", index=False)
country_sql.to_csv(RES / "conversion_by_country.csv", index=False)

# ---------------------------------------------------------------- 2. clean + SRM
df = data.clean(raw, "exclude_contaminated")
g = df.groupby("group")["converted"].agg(["size", "sum"])
n_c, x_c = int(g.loc["control", "size"]), int(g.loc["control", "sum"])
n_t, x_t = int(g.loc["treatment", "size"]), int(g.loc["treatment", "sum"])
out["clean_users"] = len(df)
out["srm"] = stats.sample_ratio_mismatch(n_c, n_t)
# Contamination share per arm (a bug that hit one arm more would bias the result)
contaminated = raw[raw.user_id.duplicated(keep=False)]
out["contaminated_rows_by_group"] = contaminated.groupby("group").size().to_dict()

# ---------------------------------------------------------------- 3. design / power
p0 = x_c / n_c
out["design"] = {
    "baseline_rate": p0,
    "days": int((df.timestamp.max() - df.timestamp.min()).days) + 1,
    "mde_abs_at_actual_n": stats.minimum_detectable_effect(p0, min(n_c, n_t)),
    "n_per_arm_for_1pct_rel_lift": stats.required_sample_size(p0, 0.01),
    "n_per_arm_for_2pct_rel_lift": stats.required_sample_size(p0, 0.02),
    "n_per_arm_for_5pct_rel_lift": stats.required_sample_size(p0, 0.05),
}
out["design"]["mde_rel_at_actual_n"] = out["design"]["mde_abs_at_actual_n"] / p0

# ---------------------------------------------------------------- 4. primary result
primary = stats.two_proportion_test(x_c, n_c, x_t, n_t)
out["primary"] = primary.as_dict()

# ---------------------------------------------------------------- 5. robustness
alt = data.clean(raw, "keep_aligned_first")
ga = alt.groupby("group")["converted"].agg(["size", "sum"])
out["sensitivity_keep_aligned_first"] = stats.two_proportion_test(
    int(ga.loc["control", "sum"]), int(ga.loc["control", "size"]),
    int(ga.loc["treatment", "sum"]), int(ga.loc["treatment", "size"])).as_dict()
out["one_sided_p_treatment_better"] = float(1 - stats.stats.norm.cdf(primary.z))
out["bayesian"] = stats.bayesian_comparison(x_c, n_c, x_t, n_t)

# Time: first half vs second half, and cumulative lift by day
df["day"] = pd.to_datetime(df["date"])
mid = df.day.min() + (df.day.max() - df.day.min()) / 2
halves = {}
for label, part in [("first_half", df[df.day <= mid]), ("second_half", df[df.day > mid])]:
    h = part.groupby("group")["converted"].agg(["size", "sum"])
    halves[label] = stats.two_proportion_test(int(h.loc["control", "sum"]), int(h.loc["control", "size"]),
                                              int(h.loc["treatment", "sum"]), int(h.loc["treatment", "size"])).as_dict()
out["time_halves"] = halves

# Segments: country, with Holm correction and a formal interaction test
seg = {}
for country, part in df.groupby("country"):
    s = part.groupby("group")["converted"].agg(["size", "sum"])
    seg[country] = stats.two_proportion_test(int(s.loc["control", "sum"]), int(s.loc["control", "size"]),
                                             int(s.loc["treatment", "sum"]), int(s.loc["treatment", "size"])).as_dict()
adj = stats.holm_adjust([seg[c]["p_value"] for c in seg])
for c, a in zip(seg, adj):
    seg[c]["p_value_holm"] = a
out["segments_country"] = seg
df["treat"] = (df["group"] == "treatment").astype(int)
full = smf.logit("converted ~ treat * C(country)", data=df).fit(disp=0)
reduced = smf.logit("converted ~ treat + C(country)", data=df).fit(disp=0)
lr = 2 * (full.llf - reduced.llf)
out["country_interaction_lr_test"] = {"lr_stat": float(lr), "df": 2,
                                      "p_value": float(stats.stats.chi2.sf(lr, 2))}

# Peeking: how often would daily checking "find" a winner when there is none?
per_day = int(round(min(n_c, n_t) / out["design"]["days"]))
out["peeking_simulation"] = stats.peeking_false_positive_rate(p0, per_day, out["design"]["days"])

# ---------------------------------------------------------------- 6. decision
practical_threshold = 0.01  # business wants at least +1% relative lift to justify the change
out["decision"] = {
    "practical_threshold_rel": practical_threshold,
    "statistically_significant": primary.p_value < 0.05,
    "ci_excludes_practical_lift": primary.rel_ci_high < practical_threshold,
    "recommendation": "Do not ship the new page" if primary.rel_ci_high < practical_threshold
                      else ("Ship" if primary.rel_ci_low > 0 else "Inconclusive: extend or redesign"),
}
(RES / "readout.json").write_text(json.dumps(out, indent=2, default=str))
print(json.dumps(out, indent=2, default=str))

# ---------------------------------------------------------------- charts
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#8a8984"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True,
})

# A. Relative lift with 95% CI vs the +1% practical bar
fig, ax = plt.subplots(figsize=(10, 3.4))
rows = [("All users (primary)", primary.as_dict())] + [(f"{c}", seg[c]) for c in ["US", "UK", "CA"]]
for i, (label, r) in enumerate(rows[::-1]):
    color = BLUE if label.startswith("All") else GRAY
    ax.plot([r["rel_ci_low"] * 100, r["rel_ci_high"] * 100], [i, i], color=color, lw=3, solid_capstyle="round")
    ax.plot(r["rel_lift"] * 100, i, "o", color=color, ms=10, mec=SURFACE, mew=2)
    ax.text(1.0, i, f'{r["rel_lift"]*100:+.1f}%   p = {r["p_value"]:.2f}', transform=ax.get_yaxis_transform(),
            va="center", ha="left", color=INK2, fontsize=9.5)
ax.axvline(0, color=INK2, lw=1)
ax.axvline(practical_threshold * 100, color=ORANGE, lw=1.5, ls="--")
ax.text(practical_threshold * 100 + 0.25, -0.55, "+1% lift needed to justify the change",
        color=ORANGE, fontsize=8.5, va="center")
ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
ax.set_xlabel("Relative lift in conversion, new page vs old (95% CI)")
ax.grid(axis="y", visible=False)
ax.set_xlim(min(r["rel_ci_low"] for _, r in rows) * 100 - 1, max(r["rel_ci_high"] for _, r in rows) * 100 + 1)
ax.set_ylim(-0.9, len(rows) - 0.5)
ax.set_title("The new page does not beat the old one, overall or in any country",
             loc="left", fontsize=12, fontweight="bold")
fig.tight_layout(rect=(0, 0, 0.87, 1))
fig.savefig(IMG / "lift_with_ci.png", dpi=160)

# B. Cumulative lift by day with CI band (stability over time)
d = df.sort_values("timestamp")
cum = []
for day in sorted(d.day.unique()):
    part = d[d.day <= day]
    s = part.groupby("group")["converted"].agg(["size", "sum"])
    r = stats.two_proportion_test(int(s.loc["control", "sum"]), int(s.loc["control", "size"]),
                                  int(s.loc["treatment", "sum"]), int(s.loc["treatment", "size"]))
    cum.append((day, r.rel_lift * 100, r.rel_ci_low * 100, r.rel_ci_high * 100))
cum = pd.DataFrame(cum, columns=["day", "lift", "lo", "hi"])
cum.to_csv(RES / "cumulative_lift.csv", index=False)
assert (cum.lo < 0).all() and (cum.hi > 0).all(), "chart title claims the CI always includes 0"
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.fill_between(cum.day, cum.lo, cum.hi, color=BLUE, alpha=0.15, lw=0)
ax.plot(cum.day, cum.lift, color=BLUE, lw=2)
ax.axhline(0, color=INK2, lw=1)
ax.set_ylabel("Cumulative relative lift (%)")
ax.set_title("The estimate settles near zero; the interval narrows but always includes 0",
             loc="left", fontsize=12, fontweight="bold")
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG / "cumulative_lift.png", dpi=160)

# C. Peeking simulation
pk = out["peeking_simulation"]
fig, ax = plt.subplots(figsize=(10, 2.8))
vals = [pk["fixed_horizon_fpr"] * 100, pk["daily_peeking_fpr"] * 100]
bars = ax.barh(["Test once at the end", f"Check daily for {pk['days']} days,\nstop at first p < 0.05"],
               vals, color=[BLUE, ORANGE], height=0.55)
for b, v in zip(bars, vals):
    ax.text(v + 0.5, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", color=INK)
ax.axvline(5, color=INK2, lw=1, ls=":")
ax.set_xlabel(f"False 'winners' in {pk['sims']:,} simulated A/A tests (no real difference)")
ax.grid(axis="y", visible=False)
ax.set_title("Why the sample size is fixed in advance: peeking daily multiplies false positives",
             loc="left", fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(IMG / "peeking_simulation.png", dpi=160)
print("charts written to", IMG)
