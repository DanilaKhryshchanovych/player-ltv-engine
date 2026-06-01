-- ============================================================
-- Query 01: 90-Day LTV Cohort Analysis
-- ============================================================
-- Business question: How much gross gaming revenue does each
-- signup cohort generate in their first 90 days after their
-- first deposit (FTD)?
--
-- Methodology:
--   · Day 0 is anchored to the player's FTD date, not signup.
--     This removes the lag between signup and first play.
--   · Only 'bet' events contribute to GGR; deposits are excluded.
--   · Players with no deposits are excluded (no FTD anchor).
--   · median_ltv_90d uses PERCENTILE_CONT to expose skew
--     from high-value outliers distorting the average.
-- ============================================================

WITH

-- Step 1: Find each player's First Time Deposit (FTD) date.
-- This is the true "Day 0" of the player lifecycle.
ftd AS (
    SELECT
        player_id,
        CAST(MIN(datetime) AS DATE) AS ftd_date
    FROM transactions
    WHERE event_type = 'deposit'
    GROUP BY player_id
),

-- Step 2: For every bet, calculate how many days after the
-- player's FTD that bet occurred.
bets_with_age AS (
    SELECT
        t.player_id,
        t.ggr,
        DATEDIFF('day', f.ftd_date, CAST(t.datetime AS DATE)) AS days_since_ftd
    FROM transactions t
    INNER JOIN ftd f ON t.player_id = f.player_id
    WHERE t.event_type = 'bet'
),

-- Step 3: Sum GGR per player within the 90-day window.
-- Players outside the window (no bets in 90 days) get 0 via the
-- outer LEFT JOIN below.
player_90d_ggr AS (
    SELECT
        player_id,
        ROUND(SUM(ggr), 2) AS ltv_90d
    FROM bets_with_age
    WHERE days_since_ftd BETWEEN 0 AND 89
    GROUP BY player_id
),

-- Step 4: Attach signup month to every player for cohort bucketing.
-- LEFT JOIN ensures players with zero bets in 90 days still appear.
cohort_base AS (
    SELECT
        p.player_id,
        DATE_TRUNC('month', p.signup_date)   AS cohort_month,
        COALESCE(g.ltv_90d, 0)               AS ltv_90d
    FROM players p
    LEFT JOIN player_90d_ggr g ON p.player_id = g.player_id
)

-- Step 5: Roll up to cohort month.
-- PERCENTILE_CONT(0.5) is the SQL-standard ordered-set aggregate
-- for median; it interpolates between the two middle values for
-- even-sized groups.
SELECT
    cohort_month,
    COUNT(*)                                                                AS total_players,
    ROUND(SUM(ltv_90d),  2)                                                AS total_ggr_90d,
    ROUND(AVG(ltv_90d),  2)                                                AS avg_ltv_90d,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ltv_90d), 2)        AS median_ltv_90d
FROM cohort_base
GROUP BY cohort_month
ORDER BY cohort_month;
