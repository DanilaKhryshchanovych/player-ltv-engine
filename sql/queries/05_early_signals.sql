-- ============================================================
-- Query 05: Early Behavioral Signals Predicting 90-Day LTV
-- ============================================================
-- Business question: Which actions in the first 7 days after
-- first deposit most strongly separate future high-value players
-- from low-value ones?
--
-- Approach:
--   1. Compute D7 behavioral features per player (bets, games,
--      sessions, avg bet size, deposit count in days 0–7).
--   2. Compute each player's 90-day LTV (total GGR from bets
--      in days 0–90 post-FTD).
--   3. Rank players by LTV using NTILE(10) into deciles, then
--      map deciles to three tiers:
--        High = deciles 9–10 (top 20%)
--        Mid  = deciles 6–8  (next 30%)
--        Low  = deciles 1–5  (bottom 50%)
--   4. Average D7 features by tier to surface predictive signals.
-- ============================================================

WITH

-- CTE 1: First Time Deposit date per player (lifecycle anchor).
ftd AS (
    SELECT
        player_id,
        CAST(MIN(datetime) AS DATE) AS ftd_date
    FROM transactions
    WHERE event_type = 'deposit'
    GROUP BY player_id
),

-- CTE 2: D7 behavioral metrics — activity in days 0–7 post-FTD.
-- NULL averages (players with zero bets in window) stay NULL so
-- they don't artificially pull down tier averages.
d7_metrics AS (
    SELECT
        t.player_id,
        COUNT(CASE WHEN t.event_type = 'bet'     THEN 1 END)            AS total_bets_d7,
        COUNT(DISTINCT CASE WHEN t.event_type = 'bet'
                            AND t.game_name <> ''
                            THEN t.game_name END)                        AS unique_games_d7,
        AVG(CASE WHEN t.event_type = 'bet' THEN t.bet_amount END)       AS avg_bet_size_d7,
        COUNT(DISTINCT CASE WHEN t.event_type = 'bet'
                            THEN t.session_id END)                       AS total_sessions_d7,
        COUNT(CASE WHEN t.event_type = 'deposit' THEN 1 END)            AS deposit_count_d7
    FROM transactions t
    INNER JOIN ftd f ON t.player_id = f.player_id
    WHERE DATEDIFF('day', f.ftd_date, CAST(t.datetime AS DATE)) BETWEEN 0 AND 7
    GROUP BY t.player_id
),

-- CTE 3: 90-day LTV per player (bet GGR only, days 0–90 post-FTD).
ltv_90d AS (
    SELECT
        t.player_id,
        ROUND(SUM(t.ggr), 2) AS ltv_90d
    FROM transactions t
    INNER JOIN ftd f ON t.player_id = f.player_id
    WHERE t.event_type = 'bet'
      AND DATEDIFF('day', f.ftd_date, CAST(t.datetime AS DATE)) BETWEEN 0 AND 89
    GROUP BY t.player_id
),

-- CTE 4: Classify every player (including those with no D7 bets)
-- into LTV deciles then map to High / Mid / Low tiers.
-- Players with no qualifying bets get ltv_90d = 0 via COALESCE.
player_tiers AS (
    SELECT
        p.player_id,
        COALESCE(l.ltv_90d, 0)                              AS ltv_90d,
        NTILE(10) OVER (ORDER BY COALESCE(l.ltv_90d, 0) ASC) AS ltv_decile
    FROM players p
    LEFT JOIN ltv_90d l ON p.player_id = l.player_id
),

tiered AS (
    SELECT
        player_id,
        ltv_90d,
        CASE
            WHEN ltv_decile >= 9 THEN 'High'   -- top 20% (deciles 9–10)
            WHEN ltv_decile >= 6 THEN 'Mid'    -- next 30% (deciles 6–8)
            ELSE                      'Low'    -- bottom 50% (deciles 1–5)
        END AS ltv_tier
    FROM player_tiers
)

-- Final: average D7 metrics broken down by LTV tier.
-- Reading across tiers reveals which early signals scale with value.
SELECT
    t.ltv_tier,
    COUNT(*)                                AS player_count,
    ROUND(AVG(d.total_bets_d7),     2)     AS avg_bets_d7,
    ROUND(AVG(d.unique_games_d7),   2)     AS avg_unique_games_d7,
    ROUND(AVG(d.avg_bet_size_d7),   2)     AS avg_bet_size_d7,
    ROUND(AVG(d.total_sessions_d7), 2)     AS avg_sessions_d7,
    ROUND(AVG(d.deposit_count_d7),  2)     AS avg_deposits_d7,
    ROUND(AVG(t.ltv_90d),           2)     AS avg_ltv_90d
FROM tiered t
LEFT JOIN d7_metrics d ON t.player_id = d.player_id
GROUP BY t.ltv_tier
ORDER BY avg_ltv_90d DESC;
