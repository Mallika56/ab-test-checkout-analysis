# Decision memo: new landing page test

**To:** Product & Growth leads · **From:** Mallika Chourasia, Data Analyst · **Test window:** 2–24 Jan 2017 (22 days)

## Recommendation

**Do not ship the new landing page.** Keep the current page, and put design effort into a different
change rather than iterating on this one.

## What we tested

Half of visitors saw the current page and half saw a redesigned one. Success metric: the share of
visitors who **converted**. Before launch, we set **+1% relative lift** as the smallest improvement
worth the cost of switching.

## Result

| | Users | Conversion |
|---|---|---|
| Current page (control) | 143,293 | **12.02%** |
| New page (treatment) | 143,397 | **11.87%** |
| Difference | | **−0.14 pts (−1.2% relative)** |

* **95% confidence interval for the relative lift: −3.2% to +0.8%.** Even the most optimistic end
  is below the +1% bar we set. So this isn't a case of "not enough data". We can rule out the gain we
  were looking for.
* p = 0.23, so not statistically significant. A Bayesian view agrees: there's only an **11.6%
  chance** the new page is better at all.

## Why we can trust it

* **Randomization worked:** a 49.98% / 50.02% split (sample-ratio check p = 0.85).
* **A logging bug was found and handled:** 3,894 users (1.3%) were recorded twice, 1,895 of them in
  both groups. They were split evenly between arms and were excluded. Keeping them the common way
  instead gives the same answer (−1.3%, p = 0.19).
* **Stable over time:** first half −0.2%, second half −2.2%. There's no sign of a novelty effect that
  would fade into a win.
* **No hidden winning segment:** US −1.8%, UK +1.2%, Canada −5.6%. None is significant after
  correcting for multiple comparisons, and the country-by-variant interaction test is p = 0.27.
* **We didn't peek:** the readout uses the full, fixed test window. A simulation on this traffic
  shows that checking daily and stopping at the first significant result would produce a false
  "winner" about 26% of the time, instead of 5%.

## Limits

* One metric only. The dataset has no revenue, order value or retention, so guardrail metrics
  couldn't be checked.
* 22 days covers three full weeks but not long-term behavior.

## Next steps

1. Roll back to 100% current page.
2. Look at *where* in the funnel the new page lost visitors (session recordings / step-level events) before
   designing the next variant.
3. Size the next test before launch. At a 12% baseline, detecting a +2% relative lift needs about
   290k users per arm; +1% needs about 1.15M per arm.
