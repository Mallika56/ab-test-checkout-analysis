-- Data-integrity checks run BEFORE looking at results.
-- In a real team these run in the warehouse. Here DuckDB reads the CSV directly.

-- 1. Is every user shown the page that matches their group?
SELECT "group", landing_page, COUNT(*) AS rows
FROM ab
GROUP BY 1, 2
ORDER BY 1, 2;

-- 2. How many users appear more than once, and how many were logged in both groups?
SELECT
  COUNT(*)                                         AS duplicate_users,
  SUM(CASE WHEN n_groups > 1 THEN 1 ELSE 0 END)    AS users_in_both_groups
FROM (
  SELECT user_id, COUNT(*) AS n_rows, COUNT(DISTINCT "group") AS n_groups
  FROM ab
  GROUP BY user_id
) per_user
WHERE n_rows > 1;
