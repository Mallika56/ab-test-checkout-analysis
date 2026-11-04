# Data

| File | Rows | Columns |
|---|---|---|
| `raw/ab_data.csv` | 294,478 | `user_id`, `timestamp`, `group` (control/treatment), `landing_page` (old_page/new_page), `converted` (0/1) |
| `raw/countries.csv` | 290,584 | `user_id`, `country` (US/UK/CA) |

**Source:** the e-commerce landing-page experiment used in Udacity's Data Analyst Nanodegree
("Analyze A/B Test Results") and redistributed on Kaggle. Udacity describes it as the results of
an e-commerce company's test of a new landing page. Its original company and collection method are
not documented, so the findings here should be read as a demonstration of experiment-analysis
method rather than a claim about a specific business.

The files are byte-identical across several independent public copies. `SHA256SUMS` records
their hashes, and CI verifies them on every run.

Time span: 2 Jan - 24 Jan 2017 (22 days).
