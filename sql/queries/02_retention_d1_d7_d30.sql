-- ============================================================
-- Query 02: Day-1 / Day-7 / Day-30 Retention Rates
-- ============================================================
-- Business question: What fraction of each signup cohort returns
-- to place at least one bet on day 1, day 7, and day 30?
--
-- Methodology:
--   · Retention anchor = player's signup_date (registration day).
--   · "Retained on Day N" means the player placed at least one bet
--     on EXACTLY day N after signup (point-in-time, not cumulative).
--   · This ensures D1 ≥ D7 ≥ D30 — the expected decreasing curve.
--     Using cumulative windows (BETWEEN 1 AND N) would inflate D7/D30
--     by including earlier activity, making D30 ≈ 100% on active
--     platforms and reversing the curve.
--   · Day 0 activity (same-day bets) is deliberately excluded
--     because it cannot distinguish a new session from the
--     onboarding flow on the same day the account was created.
--   · All 5 000 players appear in the denominator, including those
--     who never placed a bet (counted as 0 across all buckets).
-- ============================================================

WITH

-- Step 1: Collect one row per (player, bet_date) — distinct dates
-- on which the player placed at least one bet.
player_bet_dates AS (
    SELECT DISTINCT
        player_id,
        CAST(datetime AS DATE) AS bet_date
    FROM transactions
    WHERE event_type = 'bet'
),

-- Step 2: For every player compute three binary flags:
--   retained_d1  = 1 if a bet occurred on exactly day 1  after signup
--   retained_d7  = 1 if a bet occurred on exactly day 7  after signup
--   retained_d30 = 1 if a bet occurred on exactly day 30 after signup
-- Point-in-time (not cumulative) so D1 ≥ D7 ≥ D30 holds as expected.
retention_flags AS (
    SELECT
        p.player_id,
        DATE_TRUNC('month', p.signup_date)                              AS cohort_month,
        MAX(CASE
                WHEN DATEDIFF('day', p.signup_date, bd.bet_date) = 1
                THEN 1 ELSE 0
            END)                                                        AS retained_d1,
        MAX(CASE
                WHEN DATEDIFF('day', p.signup_date, bd.bet_date) = 7
                THEN 1 ELSE 0
            END)                                                        AS retained_d7,
        MAX(CASE
                WHEN DATEDIFF('day', p.signup_date, bd.bet_date) = 30
                THEN 1 ELSE 0
            END)                                                        AS retained_d30
    FROM players p
    LEFT JOIN player_bet_dates bd ON p.player_id = bd.player_id
    GROUP BY p.player_id, p.signup_date
)

-- Step 3: Aggregate flags to cohort-level percentages.
-- SUM over a 0/1 flag equals the count of retained players.
SELECT
    cohort_month,
    COUNT(*)                                                    AS total_players,
    ROUND(100.0 * SUM(retained_d1)  / COUNT(*), 2)             AS d1_retention_pct,
    ROUND(100.0 * SUM(retained_d7)  / COUNT(*), 2)             AS d7_retention_pct,
    ROUND(100.0 * SUM(retained_d30) / COUNT(*), 2)             AS d30_retention_pct
FROM retention_flags
GROUP BY cohort_month
ORDER BY cohort_month;
