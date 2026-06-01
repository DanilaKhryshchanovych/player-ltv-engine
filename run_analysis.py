"""
Player Lifetime Value Engine — DuckDB Analysis Runner
Loads players.csv + transactions.csv, executes all 5 query files,
prints results, and saves CSVs to sql/results/.
"""

import duckdb
import re
import textwrap
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────
BASE = Path(__file__).parent

con = duckdb.connect()

players_csv = str(BASE / 'data' / 'raw' / 'players.csv').replace('\\', '/')
trans_csv   = str(BASE / 'data' / 'raw' / 'transactions.csv').replace('\\', '/')

print("=" * 65)
print("  Player Lifetime Value Engine - Loading data")
print("=" * 65)

# Load players with explicit types (vip_eligible read as boolean)
con.execute(f"""
    CREATE OR REPLACE TABLE players AS
    SELECT
        CAST(player_id       AS INTEGER)  AS player_id,
        CAST(signup_date     AS DATE)     AS signup_date,
        country,
        device,
        deposit_channel,
        segment,
        CAST(vip_eligible    AS BOOLEAN)  AS vip_eligible,
        age_group
    FROM read_csv_auto('{players_csv}', header = true, all_varchar = false)
""")

# Load transactions; empty strings for game cols become NULL via NULLIF
con.execute(f"""
    CREATE OR REPLACE TABLE transactions AS
    SELECT
        CAST(transaction_id  AS BIGINT)    AS transaction_id,
        CAST(player_id       AS INTEGER)   AS player_id,
        session_id,
        CAST(datetime        AS TIMESTAMP) AS datetime,
        event_type,
        NULLIF(game_name,   '')            AS game_name,
        NULLIF(game_type,   '')            AS game_type,
        NULLIF(provider,    '')            AS provider,
        TRY_CAST(rtp AS DOUBLE)            AS rtp,
        NULLIF(volatility,  '')            AS volatility,
        CAST(bet_amount      AS DOUBLE)    AS bet_amount,
        CAST(win_amount      AS DOUBLE)    AS win_amount,
        CAST(ggr             AS DOUBLE)    AS ggr
    FROM read_csv_auto('{trans_csv}', header = true, all_varchar = true)
""")

p_cnt  = con.execute("SELECT COUNT(*) FROM players").fetchone()[0]
tx_cnt = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
print(f"  players      : {p_cnt:,} rows")
print(f"  transactions : {tx_cnt:,} rows")
print()

(BASE / 'sql' / 'results').mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────

def split_statements(sql: str) -> list[str]:
    """Split a SQL file into individual statements, ignoring ; inside comments."""
    stmts: list[str] = []
    buf: list[str] = []
    i = 0
    in_line_comment = False
    in_block_comment = False
    in_string = False

    while i < len(sql):
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            buf.append(c)
            if c == "\n":
                in_line_comment = False
        elif in_block_comment:
            buf.append(c)
            if c == "*" and nxt == "/":
                buf.append(nxt)
                i += 1
                in_block_comment = False
        elif in_string:
            buf.append(c)
            if c == "'":
                if nxt == "'":  # SQL escaped quote '' — stay inside the string
                    buf.append(nxt)
                    i += 1
                else:
                    in_string = False
        elif c == "-" and nxt == "-":
            in_line_comment = True
            buf.append(c)
        elif c == "/" and nxt == "*":
            in_block_comment = True
            buf.append(c)
        elif c == "'":
            in_string = True
            buf.append(c)
        elif c == ";":
            stmt = "".join(buf).strip()
            if stmt and re.search(r"\bSELECT\b", stmt, re.I):
                stmts.append(stmt + ";")
            buf = []
        else:
            buf.append(c)

        i += 1

    # trailing statement without semicolon
    stmt = "".join(buf).strip()
    if stmt and re.search(r"\bSELECT\b", stmt, re.I):
        stmts.append(stmt)

    return stmts


def run_query_file(label: str, sql_path: Path, result_prefix: str):
    """Execute all SELECT statements in sql_path, print results, save CSVs."""
    print("=" * 65)
    print(f"  {label}")
    print(f"  file : {sql_path}")
    print("=" * 65)

    with open(sql_path, encoding='utf-8') as f:
        sql = f.read()

    stmts = split_statements(sql)
    summary = []

    for idx, stmt in enumerate(stmts, start=1):
        suffix = "" if len(stmts) == 1 else f"_{chr(96 + idx)}"  # _a, _b ...
        out_csv = BASE / 'sql' / 'results' / f'{result_prefix}{suffix}_result.csv'

        try:
            df = con.execute(stmt).df()
        except Exception as exc:
            print(f"\n  [ERROR] Statement {idx} failed: {exc}")
            summary.append((out_csv, 0))
            continue
        row_count = len(df)

        part_label = f"Part {chr(64+idx)}" if len(stmts) > 1 else "Result"
        print(f"\n  [{part_label}]  {row_count:,} rows")
        print()

        # Print up to 10 rows with fixed column widths
        header_line = "  " + "  ".join(f"{c:<18}" for c in df.columns)
        print(header_line)
        print("  " + "-" * (len(header_line) - 2))
        for _, row in df.head(10).iterrows():
            print("  " + "  ".join(f"{str(v):<18}" for v in row))

        df.to_csv(out_csv, index=False)
        print(f"\n  Saved -> {out_csv}")
        summary.append((out_csv, row_count))

    print()
    return summary


# ── Run queries ───────────────────────────────────────────────

all_summaries = []

all_summaries += run_query_file(
    "Query 01 — 90-Day LTV Cohort Analysis",
    BASE / 'sql' / 'queries' / '01_cohort_ltv_90d.sql',
    "01"
)

all_summaries += run_query_file(
    "Query 02 — Day-1 / Day-7 / Day-30 Retention",
    BASE / 'sql' / 'queries' / '02_retention_d1_d7_d30.sql',
    "02"
)

all_summaries += run_query_file(
    "Query 03 — RFM Segmentation",
    BASE / 'sql' / 'queries' / '03_rfm_scoring.sql',
    "03"
)

all_summaries += run_query_file(
    "Query 04 — ARPPU by Game Type & Provider",
    BASE / 'sql' / 'queries' / '04_arppu_by_game_type.sql',
    "04"
)

all_summaries += run_query_file(
    "Query 05 — Early Behavioral Signals",
    BASE / 'sql' / 'queries' / '05_early_signals.sql',
    "05"
)

all_summaries += run_query_file(
    "Query 06 — Deposit Channel ROI",
    BASE / 'sql' / 'queries' / '06_deposit_channel_roi.sql',
    "06"
)

# ── Final summary ─────────────────────────────────────────────
print("=" * 65)
print("  SUMMARY")
print("=" * 65)
print()
print(f"  {'Output CSV':<45}  {'Rows':>8}")
print("  " + "-" * 56)
for path, cnt in all_summaries:
    print(f"  {path:<45}  {cnt:>8,}")

print()
print("  SQL files confirmed:")
for fn in ["sql/schema.sql",
           "sql/queries/01_cohort_ltv_90d.sql",
           "sql/queries/02_retention_d1_d7_d30.sql",
           "sql/queries/03_rfm_scoring.sql",
           "sql/queries/04_arppu_by_game_type.sql",
           "sql/queries/05_early_signals.sql",
           "sql/queries/06_deposit_channel_roi.sql"]:
    exists = "[OK]" if (BASE / fn).exists() else "[MISSING]"
    print(f"    {exists}  {fn}")

print()
print("  Done.")
