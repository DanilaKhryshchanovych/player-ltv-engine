-- ============================================================
-- Query 06: Deposit Channel ROI — LTV by Acquisition Channel
-- ============================================================
-- Business question: Which payment method at signup (card,
-- bank_transfer, ewallet, crypto) produces the highest
-- 90-day LTV, and how does deposit behaviour differ by channel?
--
-- Methodology:
--   · 90-day LTV is anchored to each player's FTD date,
--     consistent with Query 01.
--   · Only bet events contribute to LTV (GGR); deposit rows
--     are used separately to measure re-deposit behaviour.
--   · conversion_rate_pct = paying players / total players,
--     where "paying" = net positive GGR in the 90-day window.
--   · avg_deposit_volume_90d = average total USD deposited per
--     player in the 90-day window (not a per-transaction avg).
--   · All players appear in the denominator regardless of
--     whether they ever placed a bet, to capture true channel
--     conversion rates.
-- ============================================================

WITH

-- Step 1: First Time Deposit anchor per player.
ftd AS (
    SELECT
        player_id,
        CAST(MIN(datetime) AS DATE) AS ftd_date
    FROM transactions
    WHERE event_type = 'deposit'
    GROUP BY player_id
),

-- Step 2: 90-day GGR per player (bet events only, days 0–89).
player_ltv_90d AS (
    SELECT
        t.player_id,
        ROUND(SUM(t.ggr), 2) AS ltv_90d
    FROM transactions t
    INNER JOIN ftd f ON t.player_id = f.player_id
    WHERE t.event_type = 'bet'
      AND DATEDIFF('day', f.ftd_date, CAST(t.datetime AS DATE)) BETWEEN 0 AND 89
    GROUP BY t.player_id
),

-- Step 3: Deposit activity per player in the 90-day window.
-- bet_amount on deposit rows holds the deposit amount in USD.
deposit_activity AS (
    SELECT
        t.player_id,
        COUNT(*)           AS deposit_count_90d,
        SUM(t.bet_amount)  AS total_deposited_90d
    FROM transactions t
    INNER JOIN ftd f ON t.player_id = f.player_id
    WHERE t.event_type = 'deposit'
      AND DATEDIFF('day', f.ftd_date, CAST(t.datetime AS DATE)) BETWEEN 0 AND 89
    GROUP BY t.player_id
)

SELECT
    p.deposit_channel,
    COUNT(DISTINCT p.player_id)                                              AS total_players,
    COUNT(DISTINCT CASE WHEN COALESCE(l.ltv_90d, 0) > 0
                        THEN p.player_id END)                                AS paying_players,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN COALESCE(l.ltv_90d, 0) > 0
                                    THEN p.player_id END)
        / COUNT(DISTINCT p.player_id), 1)                                    AS conversion_rate_pct,
    ROUND(AVG(COALESCE(l.ltv_90d, 0)), 2)                                   AS avg_ltv_90d,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
              ORDER BY COALESCE(l.ltv_90d, 0)), 2)                           AS median_ltv_90d,
    ROUND(SUM(COALESCE(l.ltv_90d, 0)), 2)                                   AS total_ggr_90d,
    ROUND(AVG(COALESCE(d.deposit_count_90d,   0)), 2)                       AS avg_deposits_per_player,
    ROUND(AVG(COALESCE(d.total_deposited_90d, 0)), 2)                       AS avg_deposit_volume_90d
FROM players p
LEFT JOIN player_ltv_90d   l ON p.player_id = l.player_id
LEFT JOIN deposit_activity d ON p.player_id = d.player_id
GROUP BY p.deposit_channel
ORDER BY avg_ltv_90d DESC;
