"""Regenerate chart_01, chart_05, chart_06, ltv_curves with visual fixes."""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

ROOT    = Path(__file__).parent
FIGURES = ROOT / 'docs' / 'figures'

players = pd.read_csv(ROOT / 'data' / 'processed' / 'players_clean.csv', parse_dates=['signup_date'])
trans   = pd.read_parquet(ROOT / 'data' / 'processed' / 'transactions_clean.parquet')

sns.set_theme(style='whitegrid', palette='muted', font_scale=1.1)
HIGHLIGHT = '#2E86AB'
GRAY      = '#AAAAAA'
DPI = 150

bets = trans[trans['event_type'] == 'bet'].copy()
print(f"Loaded  players={players.shape}  trans={trans.shape}")

# ── chart_01: GGR by game type — fix axis labels + remove grid ─────────────
print("\n[1/4] chart_01 ...")

ggr_by_type = bets.groupby('game_type')['ggr'].sum().sort_values(ascending=True)
total_ggr   = ggr_by_type.sum()
pct         = (ggr_by_type / total_ggr * 100).round(1)
colors      = [HIGHLIGHT if i == len(ggr_by_type) - 1 else GRAY for i in range(len(ggr_by_type))]

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.barh(ggr_by_type.index, ggr_by_type.values, color=colors, edgecolor='none', height=0.6)

for bar, (gtype, val) in zip(bars, ggr_by_type.items()):
    ax.text(bar.get_width() + total_ggr * 0.005, bar.get_y() + bar.get_height() / 2,
            f'${val/1e3:.1f}k  ({pct[gtype]}%)', va='center', fontsize=10)

ax.set_xlim(0, ggr_by_type.max() * 1.22)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x/1e3:.0f}k'))
ax.grid(False)
ax.set_xlabel('Total GGR', fontsize=12)
ax.set_title('Where Does Revenue Actually Come From?\nTotal GGR by Game Type',
             fontsize=14, fontweight='bold', pad=14)
sns.despine(left=True)
ax.tick_params(left=False)
plt.tight_layout()
plt.savefig(FIGURES / 'chart_01.png', dpi=DPI, bbox_inches='tight')
plt.close()
print("  saved chart_01.png")

# ── chart_05: Churn lines — fix label overlap + remove grid ────────────────
print("[2/4] chart_05 ...")

checkpoints = [1, 3, 7, 14, 30, 60, 90]
segments    = players['segment'].unique()

first_bet  = bets.groupby('player_id')['days_since_signup'].min().rename('first_bet_day')
player_ext = players.merge(first_bet, on='player_id', how='left')
player_ext['first_bet_day'] = player_ext['first_bet_day'].fillna(9999)

retention = {}
for seg in segments:
    sp = player_ext[player_ext['segment'] == seg]
    retention[seg] = [(sp['first_bet_day'] <= d).mean() * 100 for d in checkpoints]

line_styles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1))]
seg_colors  = sns.color_palette('tab10', len(segments))

fig, ax = plt.subplots(figsize=(12, 6))
ax.grid(False)
for i, (seg, rates) in enumerate(retention.items()):
    ax.plot(checkpoints, rates, marker='o', linewidth=2.2,
            linestyle=line_styles[i % len(line_styles)],
            color=seg_colors[i], label=seg)

ax.set_xticks(checkpoints)
ax.set_xticklabels([f'Day {d}' for d in checkpoints], rotation=30, ha='right')
ax.set_ylabel('% of Players Who Have Bet At Least Once', fontsize=12)
ax.set_title('How Fast Do Players Churn After Signup?\n% Active (Placed ≥1 Bet) by Day, per Segment',
             fontsize=14, fontweight='bold', pad=14)
ax.legend(title='Segment', bbox_to_anchor=(1.02, 1), loc='upper left')
ax.yaxis.set_major_formatter(mticker.PercentFormatter())
sns.despine()
plt.tight_layout()
plt.savefig(FIGURES / 'chart_05.png', dpi=DPI, bbox_inches='tight')
plt.close()
print("  saved chart_05.png")

# ── chart_06: Provider bubble — remove background grid ─────────────────────
print("[3/4] chart_06 ...")

provider_stats = (bets.groupby('provider')
                  .agg(total_ggr=('ggr', 'sum'), total_players=('player_id', 'nunique'))
                  .reset_index())
provider_stats['arppu'] = provider_stats['total_ggr'] / provider_stats['total_players']

med_x = provider_stats['total_players'].median()
med_y = provider_stats['arppu'].median()

size_scale = ((provider_stats['total_ggr'] - provider_stats['total_ggr'].min()) /
              (provider_stats['total_ggr'].max() - provider_stats['total_ggr'].min()))
sizes = 50 + size_scale * 1200
top10 = provider_stats.nlargest(10, 'total_ggr')['provider'].tolist()

fig, ax = plt.subplots(figsize=(13, 7))
ax.grid(False)
scatter = ax.scatter(provider_stats['total_players'], provider_stats['arppu'],
                     s=sizes, c=provider_stats['total_ggr'],
                     cmap='YlOrRd', alpha=0.75, edgecolors='#555555', linewidths=0.5, zorder=3)
plt.colorbar(scatter, label='Total GGR ($)')

ax.axvline(med_x, color='#AAAAAA', linestyle='--', linewidth=1.2, zorder=2)
ax.axhline(med_y, color='#AAAAAA', linestyle='--', linewidth=1.2, zorder=2)

for _, row in provider_stats[provider_stats['provider'].isin(top10)].iterrows():
    ax.annotate(row['provider'], xy=(row['total_players'], row['arppu']),
                xytext=(5, 5), textcoords='offset points', fontsize=8.5, color='#222222')

ax.set_xlabel('Total Players (reach)', fontsize=12)
ax.set_ylabel('ARPPU — GGR per Player ($)', fontsize=12)
ax.set_title('Which Game Providers Generate the Most Revenue per Player?\nBubble size = Total GGR | Lines = median thresholds',
             fontsize=14, fontweight='bold', pad=14)
sns.despine()
plt.tight_layout()
plt.savefig(FIGURES / 'chart_06.png', dpi=DPI, bbox_inches='tight')
plt.close()
print("  saved chart_06.png")

# ── ltv_curves: Cumulative GGR by segment — remove grid ────────────────────
print("[4/4] ltv_curves ...")

# Anchor to FTD (first deposit day relative to signup), consistent with SQL queries 01/05/06
ftd_day  = (trans[trans['event_type'] == 'deposit']
            .groupby('player_id')['days_since_signup']
            .min()
            .rename('ftd_day'))
bets_ftd = bets.merge(ftd_day, on='player_id', how='left')
bets_ftd['days_since_ftd'] = bets_ftd['days_since_signup'] - bets_ftd['ftd_day']

bets_90  = bets_ftd[bets_ftd['days_since_ftd'].between(0, 89)].copy()
ltv_90d  = (bets_90.groupby('player_id')['ggr']
            .sum()
            .reindex(players['player_id'])
            .fillna(0)
            .reset_index()
            .rename(columns={'ggr': 'ltv_90d'}))
players  = players.merge(ltv_90d, on='player_id', how='left')
players['ltv_90d'] = players['ltv_90d'].fillna(0)

day_marks   = [1, 3, 7, 14, 21, 30, 45, 60, 75, 90]
seg_colors  = dict(zip(segments, sns.color_palette('tab10', len(segments))))
line_styles = {s: ls for s, ls in zip(segments, ['-', '--', '-.', ':', (0, (3, 1, 1, 1))])}
bets_seg    = bets_ftd.merge(players[['player_id', 'segment']], on='player_id', how='left')

fig, ax = plt.subplots(figsize=(14, 7))
ax.grid(False)

for seg in segments:
    sb   = bets_seg[bets_seg['segment'] == seg]
    pids = sb['player_id'].unique()
    medians, q25s, q75s = [], [], []
    for day in day_marks:
        cum = (sb[sb['days_since_ftd'] <= day]
               .groupby('player_id')['ggr'].sum()
               .reindex(pids).fillna(0))
        medians.append(cum.median())
        q25s.append(cum.quantile(0.25))
        q75s.append(cum.quantile(0.75))

    color = seg_colors[seg]
    ax.plot(day_marks, medians, color=color, linewidth=2.5,
            linestyle=line_styles[seg], marker='o', markersize=5, label=seg, zorder=4)
    ax.fill_between(day_marks, q25s, q75s, color=color, alpha=0.12, zorder=2)

ax.set_xlabel('Days Since First Deposit', fontsize=12)
ax.set_ylabel('Median Cumulative GGR per Player ($)', fontsize=12)
ax.set_title('How Does Player Value Accumulate Differently Across Segments?\nMedian cumulative GGR | Shaded band = IQR (P25–P75)',
             fontsize=14, fontweight='bold', pad=14)
ax.legend(title='Segment', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=10)
ax.set_xticks(day_marks)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'D{int(x)}'))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f'${y:.0f}'))
sns.despine()
plt.tight_layout()
plt.savefig(FIGURES / 'ltv_curves.png', dpi=DPI, bbox_inches='tight')
plt.close()
print("  saved ltv_curves.png")

print("\nAll done.")
