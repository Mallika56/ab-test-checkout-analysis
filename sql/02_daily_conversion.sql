-- Daily users and conversion rate per arm, using only clean users
-- (exactly one, correctly aligned exposure).
WITH clean AS (
  SELECT *
  FROM ab
  WHERE user_id IN (SELECT user_id FROM ab GROUP BY user_id HAVING COUNT(*) = 1)
)
SELECT
  CAST("timestamp" AS DATE)          AS day,
  "group",
  COUNT(*)                           AS users,
  SUM(converted)                     AS conversions,
  ROUND(AVG(converted), 5)           AS conversion_rate
FROM clean
GROUP BY 1, 2
ORDER BY 1, 2;
