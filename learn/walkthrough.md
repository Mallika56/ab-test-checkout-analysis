# Walkthrough: A/B test analysis

From zero. Plan on **3–4 hours**:

| Session | What | Time |
|---|---|---|
| 1 | Parts 1–2: what an A/B test is, the vocabulary | 45 min |
| 2 | Part 3: run it and read the code with this guide | 1.5 hrs |
| 3 | Parts 4–5: exercises + interview answers out loud | 1–1.5 hrs |

---

## Part 1: The idea in plain words

You change something (a new landing page) and want to know if it's *better*. You can't just launch it and
compare this month to last month, because too many other things change (season, ads, news). So you
**randomly** split visitors: half see the old page (control), half see the new one (treatment).
Randomization makes the two groups alike in every way *except* the page, so any difference in outcome
is caused by the page, plus random noise.

Statistics answers one question: **is the difference bigger than noise would produce?**

**Your 30-second pitch:**
> "I analyzed a 290k-user landing-page A/B test end to end. Before looking at results, I found a logging
> bug: 3,894 users recorded twice, about half of them in both groups. I excluded them and showed the
> answer doesn't depend on that choice. I checked randomization with a sample-ratio test, ran a
> two-proportion z-test with confidence intervals, and backed it with a Bayesian analysis, time
> stability and segment checks with multiple-comparison correction. The new page was −1.2% with a
> 95% CI up to only +0.8%, below the +1% we needed, so I recommended not shipping."

---

## Part 2: Vocabulary

| Term | Plain meaning | In this project |
|---|---|---|
| **Control / treatment** | Old version / new version | old_page / new_page |
| **Conversion rate** | Share of users who did the thing | 12.02% vs 11.87% |
| **Absolute vs relative lift** | Difference in points vs as % of control | −0.14 pts / −1.2% |
| **Null hypothesis** | "There's no real difference" | new rate = old rate |
| **p-value** | If there were truly no difference, how often would we see a gap at least this big by chance? | 0.23 (23% of the time, so not unusual) |
| **α (alpha)** | The false-positive rate you accept | 0.05 |
| **Confidence interval** | Range of lifts consistent with the data | −3.2% to +0.8% |
| **Power** | Chance of detecting a real effect of a given size | 80% |
| **MDE** | Minimum detectable effect: smallest lift the test can reliably catch | ≈2.8% relative |
| **SRM** | Sample ratio mismatch: the split isn't what was designed, so the test is broken | 49.98/50.02, fine |
| **Practical significance** | Is the lift big enough to *matter*, not just non-zero? | +1% threshold |
| **Peeking** | Checking results repeatedly and stopping when they look good | inflates false positives to ~26% |
| **Multiple comparisons** | Test many segments and some will look "significant" by luck | Holm correction |
| **Novelty effect** | Users react to change itself; effect fades | checked with time split |

---

## Part 3: Run it and read it

```bash
pip install -r requirements.txt
python -m pytest -q
python scripts/run_analysis.py
```

### `src/abtest/data.py`
* `load_raw()` joins the country file and flags `aligned`: did the user see the page their group should see?
* `integrity_report()` counts the problems. The key line is `misaligned_rows_in_non_duplicate_users`
  = **0**. That's how we know the two problems are one problem: every bad row belongs to a duplicated user.
* `clean()` has two strategies. The `assert` lines at the end are guarantees: one row per user, only
  aligned rows. If the logic ever breaks, the code stops instead of quietly producing wrong numbers.

### `src/abtest/stats.py`
* **`sample_ratio_mismatch`**: chi-square test of the observed split vs 50/50. Always run this
  *first*. If it fails, nothing else matters.
* **`required_sample_size` / `minimum_detectable_effect`**: the power formulas. Notice the tradeoff:
  halving the detectable effect needs **4×** the users (the effect is squared in the formula).
* **`two_proportion_test`**: read the docstring. The **z-test uses the pooled rate** (under the null
  both arms share one rate). The **CI uses unpooled standard errors** (we're estimating the real gap).
  Interviewers like this distinction.
* **`bayesian_comparison`**: each arm's conversion rate gets a Beta distribution (conversions + 1,
  non-conversions + 1). Draw 400,000 samples from each and count how often treatment wins. *Expected
  loss* = how much you'd lose on average if you shipped the wrong one.
* **`holm_adjust`**: sort p-values. Multiply the smallest by 3, the next by 2, the last by 1, and never let
  them decrease.
* **`peeking_false_positive_rate`**: simulates 2,000 experiments with **no** real difference, and checks
  how often each stopping rule declares a winner.

### `scripts/run_analysis.py`
Read it top to bottom: integrity → SQL cross-check (asserts pandas and DuckDB agree) → SRM → power →
primary test → sensitivity → Bayesian → time halves → segments + interaction test → peeking → decision.

The **decision rule** is explicit: if the CI's upper bound is below the practical threshold, don't
ship. If the lower bound is above 0, ship. Otherwise the test is inconclusive.

### `tests/test_stats.py`
Each hand-written formula is checked against a trusted library (statsmodels / scipy). This is how you
show you understand the math *and* that your implementation is right.

---

## Part 4: Try it yourself

1. **Change the practical threshold** to 0.5% (`practical_threshold` in `run_analysis.py`). Does the
   decision change? What would you tell the business?
2. **Compute a test by hand:** with 1,000 users per arm and 100 vs 120 conversions, compute the pooled
   rate, SE, z and p on paper. Check with `stats.two_proportion_test(100, 1000, 120, 1000)`.
3. **Power:** how many users per arm to detect +3% relative at a 12% baseline? Use
   `stats.required_sample_size(0.12, 0.03)`. How many days at this test's traffic (~6,500 users per arm per day)?
4. **SQL:** write a query returning conversion by *day of week* and arm. Is there a weekday pattern?
5. **Peeking:** run `stats.peeking_false_positive_rate(0.12, 6500, 60)`. How bad does peeking get over
   60 days?

---

## Part 5: Interview questions

**1. Walk me through how you'd analyze an A/B test.**
Check data integrity and randomization (SRM) before looking at results. Confirm the test had enough
power for the effect we care about. Run the primary test with a confidence interval. Check robustness:
alternative cleaning, time stability, segments with multiple-comparison correction. Then decide against
a practical threshold set in advance, not just p < 0.05.

**2. The p-value is 0.23. What does that mean?**
If the new page truly made no difference, we'd see a gap this large or larger about 23% of the time
just from random noise. It does *not* mean there's a 77% chance the new page is worse. For a
probability-of-better statement I'd use the Bayesian result: 11.6%.

**3. Not significant. Does that mean no effect?**
Not by itself. Absence of evidence isn't evidence of absence. That's why I look at the confidence
interval. Here it runs from −3.2% to +0.8%, so even the best case is below the +1% we needed. That
lets me say "no worthwhile effect", not just "inconclusive".

**4. What is sample ratio mismatch and why check it?**
If you design a 50/50 split but get, say, 52/48, something broke (a redirect bug, bots, logging), and
the groups may no longer be comparable. I test the split with a chi-square test. Here it was 49.98/50.02,
p = 0.85.

**5. You found duplicate users. What did you do?**
I investigated before deleting anything. All the misaligned rows belonged to users logged twice, and
half of those were in both groups, so it's an assignment bug. I excluded those users in the main
analysis, confirmed the bug affected both arms equally, and showed the common alternative cleaning
gives the same decision.

**6. The UK shows +1.2%. Should we launch in the UK only?**
No. That's cherry-picking. Test enough segments and one will look good by chance. After Holm correction
it's p = 0.55, and a formal interaction test says the effect doesn't differ by country (p = 0.27).
If the UK hypothesis matters, run a new test designed for it.

**7. Why not stop the test as soon as it's significant?**
Peeking. Each check is another chance for noise to cross the line. My simulation with this test's
traffic: one check gives a 4.6% false-positive rate; checking daily for 22 days gives 25.6%. Fix the
sample size up front, or use a sequential method designed for repeated looks.

**8. How would you size the next test?**
Pick the smallest lift worth acting on, then use the power formula. At a 12% baseline, +2% relative
needs about 290k users per arm and +1% needs about 1.15M. Then translate that into days of traffic and
check it's feasible.

---

## Resume bullets (pick 2)

- Analyzed a 290k-user e-commerce A/B test end to end (SRM check, power analysis, two-proportion z-test,
  Bayesian Beta-Binomial, Holm-corrected segments, logistic interaction test) and recommended against
  launch: −1.2% lift, 95% CI upper bound +0.8%, below the +1% threshold
- Found a logging bug affecting 1.3% of users (duplicate and cross-group assignment), showed it hit both arms
  equally and didn't change the decision, and cross-validated integrity checks in Python and SQL
- Simulated 2,000 A/A tests to show daily peeking inflates false positives from 4.6% to 25.6%; built a
  tested Python stats toolkit validated against statsmodels and scipy
