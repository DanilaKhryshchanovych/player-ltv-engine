-- ============================================================
-- Query 04: ARPPU by Game Type and Provider
-- ============================================================
-- Business question: Which game categories and software providers
-- generate the most revenue per paying user?
--
-- ARPPU = Average Revenue Per Paying User
--       = total GGR / distinct paying players
--
-- "Paying" is defined as players who generated NET POSITIVE GGR
-- over their lifetime (i.e. the house made money from them).
-- Players with net negative GGR (consistent winners) are excluded
-- because their presence would distort per-unit revenue metrics.
--
-- Only bet events are included; deposit rows carry no game context.
-- ============================================================

-- ── Query A: ARPPU by game type ───────────────────────────────

WITH

-- Identify players who are net profitable for the casino
paying_players AS (
    SELECT player_id
    FROM transactions
    WHERE event_type = 'bet'
    GROUP BY player_id
    HAVING SUM(ggr) > 0
)

SELECT
    game_type,
    ROUND(SUM(t.ggr),                         2)  AS total_ggr,
    COUNT(DISTINCT t.player_id)                    AS total_players,
    ROUND(SUM(t.ggr) /
          COUNT(DISTINCT t.player_id),        2)   AS arppu,
    ROUND(AVG(t.bet_amount),                  2)  AS avg_bet_size,
    ROUND(AVG(t.rtp),                         2)  AS avg_rtp,
    COUNT(DISTINCT t.session_id)                   AS total_sessions
FROM transactions t
INNER JOIN paying_players pp ON t.player_id = pp.player_id
WHERE t.event_type   = 'bet'
  AND t.game_type   IS NOT NULL
GROUP BY t.game_type
HAVING SUM(t.ggr) > 0
ORDER BY total_ggr DESC;


-- ── Query B: ARPPU by provider (top 15 by GGR) ───────────────

WITH

paying_players AS (
    SELECT player_id
    FROM transactions
    WHERE event_type = 'bet'
    GROUP BY player_id
    HAVING SUM(ggr) > 0
)

SELECT
    t.provider,
    ROUND(SUM(t.ggr),                         2)  AS total_ggr,
    COUNT(DISTINCT t.player_id)                    AS total_players,
    ROUND(SUM(t.ggr) /
          COUNT(DISTINCT t.player_id),        2)   AS arppu,
    ROUND(AVG(t.bet_amount),                  2)  AS avg_bet_size,
    ROUND(AVG(t.rtp),                         2)  AS avg_rtp,
    COUNT(DISTINCT t.session_id)                   AS total_sessions
FROM transactions t
INNER JOIN paying_players pp ON t.player_id = pp.player_id
WHERE t.event_type  = 'bet'
  AND t.provider   IS NOT NULL
GROUP BY t.provider
HAVING SUM(t.ggr) > 0
ORDER BY total_ggr DESC
LIMIT 15;
