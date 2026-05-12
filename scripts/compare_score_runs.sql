-- Side-by-side comparison of the pre-Sonnet-4.6 base scores
-- (snapshot in score_snapshot_pre_sonnet46) vs the current scores
-- in seen_jobs.

-- 1. Summary: counts + score moments
.headers on
.mode column
.width 28 8

SELECT 'snapshot rows'                AS metric, COUNT(*)             AS value FROM score_snapshot_pre_sonnet46
UNION ALL
SELECT 'current scored rows',                COUNT(*)                 FROM seen_jobs WHERE score IS NOT NULL
UNION ALL
SELECT 'snapshot mean',                ROUND(AVG(score_old),1)        FROM score_snapshot_pre_sonnet46
UNION ALL
SELECT 'current mean',                 ROUND(AVG(score),1)            FROM seen_jobs WHERE score IS NOT NULL
UNION ALL
SELECT 'snapshot median (approx)',    (SELECT score_old FROM score_snapshot_pre_sonnet46 ORDER BY score_old LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM score_snapshot_pre_sonnet46))
UNION ALL
SELECT 'current median (approx)',     (SELECT score FROM seen_jobs WHERE score IS NOT NULL ORDER BY score LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM seen_jobs WHERE score IS NOT NULL))
UNION ALL
SELECT 'paired rows (in both)',       COUNT(*)
  FROM score_snapshot_pre_sonnet46 s
  JOIN seen_jobs j ON j.id = s.id
  WHERE j.score IS NOT NULL
UNION ALL
SELECT 'mean delta (new - old)',      ROUND(AVG(j.score - s.score_old),1)
  FROM score_snapshot_pre_sonnet46 s
  JOIN seen_jobs j ON j.id = s.id
  WHERE j.score IS NOT NULL
UNION ALL
SELECT 'rows now cannot_score',       COUNT(*)
  FROM score_snapshot_pre_sonnet46 s
  JOIN seen_jobs j ON j.id = s.id
  WHERE j.score IS NULL AND j.status LIKE 'cannot_score:%';

.print ""
.print "=== histogram (old vs new) ==="
.width 12 10 10
SELECT
  bucket AS bucket,
  SUM(CASE WHEN src='old' THEN 1 ELSE 0 END) AS old_count,
  SUM(CASE WHEN src='new' THEN 1 ELSE 0 END) AS new_count
FROM (
  SELECT CASE
    WHEN score_old < 30 THEN '00-29'
    WHEN score_old < 40 THEN '30-39'
    WHEN score_old < 50 THEN '40-49'
    WHEN score_old < 60 THEN '50-59'
    WHEN score_old < 70 THEN '60-69'
    WHEN score_old < 80 THEN '70-79'
    WHEN score_old < 90 THEN '80-89'
    ELSE '90-100' END AS bucket,
  'old' AS src FROM score_snapshot_pre_sonnet46
  UNION ALL
  SELECT CASE
    WHEN score < 30 THEN '00-29'
    WHEN score < 40 THEN '30-39'
    WHEN score < 50 THEN '40-49'
    WHEN score < 60 THEN '50-59'
    WHEN score < 70 THEN '60-69'
    WHEN score < 80 THEN '70-79'
    WHEN score < 90 THEN '80-89'
    ELSE '90-100' END AS bucket,
  'new' AS src FROM seen_jobs WHERE score IS NOT NULL
)
GROUP BY bucket ORDER BY bucket;

.print ""
.print "=== biggest score INCREASES (top 15) ==="
.width 6 6 6 24 40
SELECT s.score_old AS old, j.score AS new, (j.score - s.score_old) AS delta,
       SUBSTR(j.company,1,22) AS company, SUBSTR(j.title,1,38) AS title
FROM score_snapshot_pre_sonnet46 s
JOIN seen_jobs j ON j.id = s.id
WHERE j.score IS NOT NULL
ORDER BY (j.score - s.score_old) DESC, j.score DESC
LIMIT 15;

.print ""
.print "=== biggest score DECREASES (top 15) ==="
SELECT s.score_old AS old, j.score AS new, (j.score - s.score_old) AS delta,
       SUBSTR(j.company,1,22) AS company, SUBSTR(j.title,1,38) AS title
FROM score_snapshot_pre_sonnet46 s
JOIN seen_jobs j ON j.id = s.id
WHERE j.score IS NOT NULL
ORDER BY (j.score - s.score_old) ASC, j.score ASC
LIMIT 15;

.print ""
.print "=== rows that LOST a score (now cannot_score) ==="
SELECT s.score_old AS old, j.status AS new_status,
       SUBSTR(j.company,1,22) AS company, SUBSTR(j.title,1,38) AS title
FROM score_snapshot_pre_sonnet46 s
JOIN seen_jobs j ON j.id = s.id
WHERE j.score IS NULL
ORDER BY s.score_old DESC
LIMIT 20;
