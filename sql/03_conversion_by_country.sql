-- Conversion by country and arm (clean users), joined to the country lookup.
WITH clean AS (
  SELECT *
  FROM ab
  WHERE user_id IN (SELECT user_id FROM ab GROUP BY user_id HAVING COUNT(*) = 1)
)
SELECT
  countries.country,
  clean."group",
  COUNT(*)                     AS users,
  SUM(clean.converted)         AS conversions,
  ROUND(AVG(clean.converted), 5) AS conversion_rate
FROM clean
JOIN countries USING (user_id)
GROUP BY 1, 2
ORDER BY 1, 2;
