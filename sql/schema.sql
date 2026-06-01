-- ============================================================
-- Player Lifetime Value Engine — Schema Definition
-- iGaming Analytics Portfolio Project
-- ============================================================
-- Run this file first to create the two core tables.
-- Data is loaded separately via COPY or read_csv_auto.
-- ============================================================

-- Drop and recreate for idempotent runs
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS players;

-- ── players ──────────────────────────────────────────────────
-- One row per registered account. Signup date anchors all
-- cohort windows; segment is the CRM label at registration.
CREATE TABLE players (
    player_id        INTEGER     NOT NULL,   -- Unique player identifier (PK)
    signup_date      DATE        NOT NULL,   -- Date of account registration (UTC day)
    country          VARCHAR(2),             -- ISO-3166 alpha-2 country code (e.g. 'GB')
    device           VARCHAR,                -- Primary device: 'mobile' | 'desktop' | 'tablet'
    deposit_channel  VARCHAR,                -- First-deposit payment method: 'card' | 'ewallet' | 'crypto' | 'bank_transfer'
    segment          VARCHAR,                -- CRM lifecycle segment assigned at registration
    vip_eligible     BOOLEAN,                -- TRUE if player qualifies for VIP programme
    age_group        VARCHAR,                -- Age bracket string (e.g. '25-34', '35-44')
    PRIMARY KEY (player_id)
);

-- ── transactions ──────────────────────────────────────────────
-- One row per game round (event_type='bet') or wallet top-up
-- (event_type='deposit'). Game/provider columns are NULL for
-- deposit events. GGR = bet_amount − win_amount; negative values
-- mean the house paid out more than it received on that event.
CREATE TABLE transactions (
    transaction_id   BIGINT      NOT NULL,   -- Unique event identifier (PK)
    player_id        INTEGER     NOT NULL,   -- FK → players.player_id
    session_id       VARCHAR     NOT NULL,   -- Session grouping key (<player_id>_<seq>)
    datetime         TIMESTAMP   NOT NULL,   -- Event timestamp (UTC)
    event_type       VARCHAR(10) NOT NULL,   -- 'bet' | 'deposit'
    game_name        VARCHAR,                -- Game title; NULL for deposit events
    game_type        VARCHAR,                -- Category: 'slot' | 'live' | 'table' | 'crash' | 'poker' | 'bingo' | 'scratch'; NULL for deposits
    provider         VARCHAR,                -- Software studio / provider name; NULL for deposits
    rtp              DOUBLE,                 -- Configured Return-to-Player % for this game round; NULL for deposits
    volatility       VARCHAR,                -- Volatility band: 'Low' | 'Medium' | 'High'; NULL for deposits
    bet_amount       DOUBLE,                 -- Amount wagered (player units); equals deposit amount for deposit events
    win_amount       DOUBLE,                 -- Amount returned to player; 0 for deposits
    ggr              DOUBLE,                 -- Gross Gaming Revenue: bet_amount − win_amount (casino POV)
    PRIMARY KEY (transaction_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

-- ── Load data (DuckDB CLI / runner) ─────────────────────────
-- COPY players      FROM 'players.csv'      (HEADER TRUE, AUTO_DETECT TRUE);
-- COPY transactions FROM 'transactions.csv' (HEADER TRUE, AUTO_DETECT TRUE);
