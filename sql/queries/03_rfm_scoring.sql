-- ============================================================
-- Query 03: RFM Segmentation
-- ============================================================
-- Business question: Which players are Champions / at-risk /
-- lapsed based on their betting recency, frequency, and value?
--
-- Dimensions:
--   Recency  (R) — days since last bet        (lower = better)
--   Frequency(F) — total distinct bet sessions (higher = better)
--   Monetary (M) — total GGR generated        (higher = better)
--
-- Each dimension is scored 1–5 with NTILE(5):
--   · R: ORDER BY recency_days DESC → bucket 1=stale, 5=fresh
--   · F: ORDER BY frequency       ASC → bucket 1=rare,  5=frequent
--   · M: ORDER BY monetary        ASC → bucket 1=low,   5=high
--
-- Segment labels (priority order, first match wins):
--   Champions  — R+F+M >= 12  (top performers across all dimensions)
--   Loyal      — R+F+M >= 9   (strong all-round)
--   Promising  — R>=4, M<=2   (recently active but low spenders)
--   At Risk    — R<=2, F>=3   (high frequency but going cold)
--   Hibernating— everyone else
-- ============================================================

-- ── Part A: Main RFM result ───────────────────────────────────

WITH

-- Step 1: Snapshot date (latest event in the dataset).
-- Using a subquery rather than hardcoding a date keeps this
-- query reproducible as new data is appended.
reference_date AS (
    SELECT CAST(MAX(datetime) AS DATE) AS snapshot_date
    FROM transactions
),

-- Step 2: Raw RFM metrics per player (bet events only).
player_rfm_raw AS (
    SELECT
        t.player_id,
        DATEDIFF(
            'day',
            CAST(MAX(t.datetime) AS DATE),
            (SELECT snapshot_date FROM reference_date)
        )                                           AS recency_days,   -- days since last bet
        COUNT(DISTINCT t.session_id)                AS frequency,       -- number of distinct bet sessions
        ROUND(SUM(t.ggr), 2)                        AS monetary         -- total GGR (casino POV)
    FROM transactions t
    WHERE t.event_type = 'bet'
    GROUP BY t.player_id
),

-- Step 3: Score each dimension 1–5 using NTILE window function.
rfm_scored AS (
    SELECT
        player_id,
        recency_days,
        frequency,
        monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC)  AS r_score,  -- 5 = most recent
        NTILE(5) OVER (ORDER BY frequency       ASC)  AS f_score,  -- 5 = most sessions
        NTILE(5) OVER (ORDER BY monetary        ASC)  AS m_score   -- 5 = most GGR
    FROM player_rfm_raw
),

-- Step 4: Apply segment labels based on score combinations.
rfm_labeled AS (
    SELECT
        player_id,
        r_score,
        f_score,
        m_score,
        r_score + f_score + m_score                 AS rfm_total,
        CASE
            WHEN r_score + f_score + m_score >= 12  THEN 'Champions'
            WHEN r_score + f_score + m_score >= 9   THEN 'Loyal'
            WHEN r_score >= 4 AND m_score <= 2      THEN 'Promising'
            WHEN r_score <= 2 AND f_score >= 3      THEN 'At Risk'
            ELSE                                         'Hibernating'
        END                                         AS rfm_segment
    FROM rfm_scored
)

-- Final: join CRM segment from players table for comparison.
-- LEFT JOIN ensures players with no bet history are included;
-- they receive Hibernating as their computed segment (score = 0).
SELECT
    p.player_id,
    COALESCE(r.r_score,     0)              AS r_score,
    COALESCE(r.f_score,     0)              AS f_score,
    COALESCE(r.m_score,     0)              AS m_score,
    COALESCE(r.rfm_total,   0)              AS rfm_total,
    COALESCE(r.rfm_segment, 'Hibernating')  AS rfm_segment,
    p.segment                               AS actual_segment
FROM players p
LEFT JOIN rfm_labeled r ON r.player_id = p.player_id
ORDER BY COALESCE(r.rfm_total, 0) DESC, p.player_id;


-- ── Part B: Validation — RFM segment vs CRM segment ──────────
-- Shows the cross-tabulation of computed RFM labels against the
-- original CRM segment, plus an overall exact-match percentage.

WITH

reference_date AS (
    SELECT CAST(MAX(datetime) AS DATE) AS snapshot_date
    FROM transactions
),
player_rfm_raw AS (
    SELECT
        t.player_id,
        DATEDIFF('day', CAST(MAX(t.datetime) AS DATE),
                 (SELECT snapshot_date FROM reference_date)) AS recency_days,
        COUNT(DISTINCT t.session_id)                         AS frequency,
        ROUND(SUM(t.ggr), 2)                                 AS monetary
    FROM transactions t
    WHERE t.event_type = 'bet'
    GROUP BY t.player_id
),
rfm_scored AS (
    SELECT
        player_id,
        NTILE(5) OVER (ORDER BY recency_days DESC)   AS r_score,
        NTILE(5) OVER (ORDER BY frequency       ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary        ASC) AS m_score
    FROM player_rfm_raw
),
rfm_labeled AS (
    SELECT
        player_id,
        CASE
            WHEN r_score + f_score + m_score >= 12  THEN 'Champions'
            WHEN r_score + f_score + m_score >= 9   THEN 'Loyal'
            WHEN r_score >= 4 AND m_score <= 2      THEN 'Promising'
            WHEN r_score <= 2 AND f_score >= 3      THEN 'At Risk'
            ELSE                                         'Hibernating'
        END AS rfm_segment
    FROM rfm_scored
),
joined AS (
    SELECT
        COALESCE(r.rfm_segment, 'Hibernating')                              AS rfm_segment,
        p.segment                                                            AS actual_segment,
        CASE WHEN COALESCE(r.rfm_segment, 'Hibernating') = p.segment
             THEN 1 ELSE 0 END                                              AS is_match
    FROM players p
    LEFT JOIN rfm_labeled r ON r.player_id = p.player_id
)

SELECT
    rfm_segment,
    actual_segment,
    COUNT(*)                                                        AS player_count,
    ROUND(100.0 * COUNT(*) /
          SUM(COUNT(*)) OVER (PARTITION BY rfm_segment), 2)        AS pct_of_rfm_segment,
    ROUND(100.0 * SUM(is_match) / COUNT(*), 2)                     AS exact_match_pct
FROM joined
GROUP BY rfm_segment, actual_segment
ORDER BY rfm_segment, player_count DESC;
