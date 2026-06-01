import json
import math
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE = Path(__file__).parent
OUT  = BASE / 'docs' / 'dashboard.html'
OUT.parent.mkdir(parents=True, exist_ok=True)

SEG_CLR = {
    'Champions':  '#F59E0B',
    'Loyal':      '#3B82F6',
    'Promising':  '#059669',
    'At Risk':    '#DC2626',
    'Hibernating':'#94A3B8',
}
GAME_CLR = {'slot': '#3B82F6', 'live': '#F59E0B', 'table': '#059669', 'poker': '#8B5CF6'}
SEGS = list(SEG_CLR.keys())

def hex_rgba(h, a=0.14):
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{a})'

def safe(v):
    return 0.0 if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)

# ── Load ──────────────────────────────────────────────────────────────────────
players = pd.read_csv(BASE / 'data' / 'processed' / 'players_clean.csv', parse_dates=['signup_date'])
txn     = pd.read_parquet(BASE / 'data' / 'processed' / 'transactions_clean.parquet')
cohort  = pd.read_csv(BASE / 'sql' / 'results' / '01_result.csv', parse_dates=['cohort_month'])
ret     = pd.read_csv(BASE / 'sql' / 'results' / '02_result.csv', parse_dates=['cohort_month'])
ggr_g   = pd.read_csv(BASE / 'sql' / 'results' / '04_a_result.csv')
tier    = pd.read_csv(BASE / 'sql' / 'results' / '05_result.csv')

if txn['datetime'].dtype == object:
    txn['datetime'] = pd.to_datetime(txn['datetime'])

# ── Derived ───────────────────────────────────────────────────────────────────
bets = txn[txn['event_type'] == 'bet'].copy()
bets = bets.merge(players[['player_id', 'segment']], on='player_id', how='left')

full_cohorts = cohort[cohort['total_players'] > 50].reset_index(drop=True)
ret_f        = ret[ret['total_players'] > 50].reset_index(drop=True)

date_min = players['signup_date'].min().strftime('%b %Y')
date_max = players['signup_date'].max().strftime('%b %Y')

# KPI helper — returns dict for the JS slicer
def compute_kpis(coh_df, ret_df, n_players):
    vc = coh_df[coh_df['total_players'] > 10].reset_index(drop=True)
    vr = ret_df[ret_df['total_players'] > 10].reset_index(drop=True)
    avg_ltv = safe(vc['avg_ltv_90d'].mean())
    avg_d30 = safe(vr['d30_retention_pct'].mean())
    return {
        'total_players': int(n_players),
        'total_ggr':     safe(coh_df['total_ggr_90d'].sum()),
        'avg_ltv':       round(avg_ltv, 2),
        'avg_d30':       round(avg_d30, 1),
    }

kpi_data = {
    'all':  compute_kpis(full_cohorts, ret_f, len(players)),
    '2023': compute_kpis(
        cohort[cohort['cohort_month'].dt.year == 2023],
        ret[ret['cohort_month'].dt.year == 2023],
        len(players[players['signup_date'].dt.year == 2023])
    ),
    '2024': compute_kpis(
        cohort[cohort['cohort_month'].dt.year == 2024],
        ret[ret['cohort_month'].dt.year == 2024],
        len(players[players['signup_date'].dt.year == 2024])
    ),
}

# GGR bar
ggr_main   = ggr_g[ggr_g['game_type'].isin(GAME_CLR)].sort_values('total_ggr', ascending=False).reset_index(drop=True)
bar_colors = [GAME_CLR[gt] for gt in ggr_main['game_type']]

# Segment donut
seg_cnt = players['segment'].value_counts().reset_index()
seg_cnt.columns = ['segment', 'count']
seg_cnt_dict = dict(zip(seg_cnt['segment'], seg_cnt['count'].astype(int)))

# Retention heatmap — pre-compute for all / 2023 / 2024
def make_hm(df):
    df = df[df['total_players'] > 5].copy()
    df = df.sort_values('cohort_month', ascending=True)
    df['label'] = df['cohort_month'].dt.strftime("%b '%y")
    z    = df[['d1_retention_pct', 'd7_retention_pct', 'd30_retention_pct']].values.tolist()
    text = [[f'{v:.1f}%' for v in row] for row in z]
    return {'z': z, 'y': df['label'].tolist(), 'text': text}

hm_data = {
    'all':  make_hm(ret),
    '2023': make_hm(ret[ret['cohort_month'].dt.year == 2023]),
    '2024': make_hm(ret[ret['cohort_month'].dt.year == 2024]),
}

# LTV curves — cumulative GGR by segment at D1–D90 checkpoints
checkpoints = [1, 3, 7, 14, 21, 30, 45, 60, 75, 90]
bets90 = bets[bets['days_since_signup'].between(0, 90)].copy()
parts  = []
for d in checkpoints:
    sub = (bets90[bets90['days_since_signup'] <= d]
           .groupby(['player_id', 'segment'])['ggr'].sum().reset_index())
    sub['day'] = d
    parts.append(sub)
ltv_df    = pd.concat(parts, ignore_index=True)
ltv_stats = ltv_df.groupby(['segment', 'day']).agg(
    median=('ggr', 'median'),
    p25=('ggr', lambda x: x.quantile(0.25)),
    p75=('ggr', lambda x: x.quantile(0.75)),
).reset_index()

# RFM scatter
max_ts  = bets['datetime'].max()
rfm_raw = bets.groupby(['player_id', 'segment']).agg(
    recency  =('datetime',   lambda x: (max_ts - x.max()).days),
    frequency=('session_id', 'nunique'),
    monetary =('ggr',        'sum'),
).reset_index()
rfm_raw = rfm_raw[rfm_raw['monetary'] > 0].copy()
rfm_raw['mc'] = rfm_raw['monetary'].clip(upper=rfm_raw['monetary'].quantile(0.99))
rfm_raw['sz'] = 4 + 14 * (rfm_raw['frequency'] / rfm_raw['frequency'].max())

# LTV tier
tier_ord = ['High', 'Mid', 'Low']
tier_f   = tier.set_index('ltv_tier').loc[tier_ord].reset_index()

# ── Filter-grid helpers ───────────────────────────────────────────────────────

def compute_seg_kpis(p_df, b_df):
    n = len(p_df)
    if n == 0:
        return {'total_players': 0, 'total_ggr': 0.0, 'avg_ltv': 0.0, 'avg_d30': 0.0}
    b90       = b_df[b_df['days_since_signup'] <= 90]
    total_ggr = safe(b90['ggr'].sum())
    avg_ltv   = round(total_ggr / n, 2)
    cutoff    = max_ts - pd.Timedelta(days=27)
    eligible  = p_df[p_df['signup_date'] <= cutoff]
    if len(eligible) > 0:
        elig_ids   = set(eligible['player_id'])
        active_d30 = b_df[
            b_df['player_id'].isin(elig_ids) &
            b_df['days_since_signup'].between(27, 33)
        ]['player_id'].nunique()
        avg_d30 = round(100 * active_d30 / len(eligible), 1)
    else:
        avg_d30 = 0.0
    return {'total_players': n, 'total_ggr': round(total_ggr, 2),
            'avg_ltv': avg_ltv, 'avg_d30': avg_d30}


def make_ltv_data(bets_df):
    chk = [1, 3, 7, 14, 21, 30, 45, 60, 75, 90]
    b90 = bets_df[bets_df['days_since_signup'].between(0, 90)].copy()
    parts = []
    for d in chk:
        sub = (b90[b90['days_since_signup'] <= d]
               .groupby(['player_id', 'segment'])['ggr'].sum().reset_index())
        sub['day'] = d
        parts.append(sub)
    if not parts:
        return {}, {}
    ltv_df = pd.concat(parts, ignore_index=True)
    stats  = ltv_df.groupby(['segment', 'day']).agg(
        median=('ggr', 'median'),
        p25=('ggr', lambda x: x.quantile(0.25)),
        p75=('ggr', lambda x: x.quantile(0.75)),
    ).reset_index()
    lines, bands = {}, {}
    for seg in SEGS:
        sub = stats[stats['segment'] == seg].sort_values('day')
        if sub.empty: continue
        lines[seg] = {'x': sub['day'].tolist(), 'y': [round(v, 4) for v in sub['median']]}
        x_b = sub['day'].tolist() + sub['day'].tolist()[::-1]
        y_b = sub['p75'].tolist() + sub['p25'].tolist()[::-1]
        bands[seg] = {'x': x_b, 'y': [round(v, 4) for v in y_b]}
    return lines, bands


def make_rfm_data(bets_df):
    rfm = bets_df.groupby(['player_id', 'segment']).agg(
        recency  =('datetime',   lambda x: (max_ts - x.max()).days),
        frequency=('session_id', 'nunique'),
        monetary =('ggr',        'sum'),
    ).reset_index()
    rfm = rfm[rfm['monetary'] > 0].copy()
    if rfm.empty: return {}
    rfm['mc'] = rfm['monetary'].clip(upper=rfm['monetary'].quantile(0.99))
    rfm['sz'] = 4 + 14 * (rfm['frequency'] / rfm['frequency'].max())
    result = {}
    for seg in SEGS:
        sub = rfm[rfm['segment'] == seg]
        if sub.empty: continue
        result[seg] = {
            'x':    sub['recency'].tolist(),
            'y':    [round(v, 2) for v in sub['mc']],
            'sz':   [round(v, 2) for v in sub['sz']],
            'text': sub['frequency'].astype(str).tolist(),
        }
    return result


def make_ggr_bar_data(bets_df):
    if 'game_type' not in bets_df.columns: return None
    b90 = bets_df[bets_df['days_since_signup'] <= 90]
    ggr = (b90.groupby('game_type')['ggr'].sum().reset_index()
           .rename(columns={'ggr': 'total_ggr'}))
    ggr = ggr[ggr['game_type'].isin(GAME_CLR)].sort_values('total_ggr', ascending=False)
    if ggr.empty: return None
    return {
        'x':      [gt.title() for gt in ggr['game_type']],
        'y':      [round(v, 2) for v in ggr['total_ggr']],
        'colors': [GAME_CLR[gt] for gt in ggr['game_type']],
        'text':   [f'€{v:,.0f}' for v in ggr['total_ggr']],
    }


year_players = {
    'all':  players,
    '2023': players[players['signup_date'].dt.year == 2023],
    '2024': players[players['signup_date'].dt.year == 2024],
}
kpi_grid   = {}
chart_data = {}
for yr_key, p_yr in year_players.items():
    yr_ids = set(p_yr['player_id'])
    b_yr   = bets[bets['player_id'].isin(yr_ids)]
    kpi_grid[yr_key] = {
        seg: compute_seg_kpis(p_yr[p_yr['segment'] == seg], b_yr[b_yr['segment'] == seg])
        for seg in SEGS
    }
    ltv_lines, ltv_bands = make_ltv_data(b_yr)
    chart_data[yr_key] = {
        'ltv_lines': ltv_lines,
        'ltv_bands': ltv_bands,
        'scatter':   make_rfm_data(b_yr),
        'donut':     {seg: int((p_yr['segment'] == seg).sum()) for seg in SEGS},
        'ggr_bar':   make_ggr_bar_data(b_yr),
    }

# ── Subplots ──────────────────────────────────────────────────────────────────
specs = [
    [{"type":"indicator"},{"type":"indicator"},{"type":"indicator"},{"type":"indicator"}],
    [{"type":"xy","colspan":2}, None, {"type":"domain","colspan":2}, None],
    [{"type":"xy","colspan":2}, None, {"type":"xy","colspan":2}, None],
    [{"type":"xy","colspan":2}, None, {"type":"xy","colspan":2}, None],
]

subplot_titles = [
    '','','','',
    'Which game type generates the most revenue?',
    'How are players distributed across lifecycle segments?',
    'Are we retaining players month over month?',
    'Do high-value players compound revenue faster?',
    'Who are our most valuable players by RFM profile?',
    'What D7 behaviours predict top-tier lifetime value?',
]

fig = make_subplots(
    rows=4, cols=4,
    specs=specs,
    subplot_titles=subplot_titles,
    row_heights=[0.09, 0.27, 0.32, 0.32],
    vertical_spacing=0.07,
    horizontal_spacing=0.05,
)

# Track trace indices for JS slicers
t = 0
trace_map = {}

# ── Row 1: KPI indicators ─────────────────────────────────────────────────────
kpi_configs = [
    dict(value=kpi_data['all']['total_players'], title='Total Players',     color='#2563EB', fmt=',d',  prefix='', suffix=''),
    dict(value=kpi_data['all']['total_ggr'],     title='Total GGR (90d)',   color='#059669', fmt=',.0f',prefix='€',suffix=''),
    dict(value=kpi_data['all']['avg_ltv'],        title='Avg 90d LTV',      color='#7C3AED', fmt='.2f', prefix='€',suffix=''),
    dict(value=kpi_data['all']['avg_d30'],        title='Avg D30 Retention',color='#DC2626', fmt='.1f', prefix='', suffix='%'),
]
trace_map['kpi'] = list(range(4))
for i, k in enumerate(kpi_configs):
    fig.add_trace(go.Indicator(
        mode='number',
        value=k['value'],
        title=dict(text=f"<b>{k['title']}</b>", font=dict(size=12, color='#64748B')),
        number=dict(font=dict(size=32, color=k['color']),
                    prefix=k['prefix'], suffix=k['suffix'], valueformat=k['fmt']),
    ), row=1, col=i + 1)
    t += 1

# ── Row 2: GGR bar ────────────────────────────────────────────────────────────
fig.add_trace(go.Bar(
    x=ggr_main['game_type'].str.title(),
    y=ggr_main['total_ggr'],
    marker=dict(color=bar_colors, line=dict(width=0), opacity=0.85),
    text=[f'€{v:,.0f}' for v in ggr_main['total_ggr']],
    textposition='outside',
    textfont=dict(color='#374151', size=11, family='Inter'),
    customdata=ggr_main[['total_players', 'arppu']].values,
    hovertemplate=(
        '<b>%{x}</b><br>GGR: €%{y:,.0f}<br>'
        'Players: %{customdata[0]:,.0f}<br>'
        'ARPPU: €%{customdata[1]:.2f}<extra></extra>'
    ),
    showlegend=False,
), row=2, col=1)
trace_map['ggr_bar'] = t
t += 1

# ── Row 2: Segment donut ──────────────────────────────────────────────────────
fig.add_trace(go.Pie(
    labels=seg_cnt['segment'],
    values=seg_cnt['count'],
    hole=0.55,
    marker=dict(
        colors=[SEG_CLR.get(s, '#94A3B8') for s in seg_cnt['segment']],
        line=dict(color='white', width=2),
    ),
    textinfo='label+percent',
    textfont=dict(size=11, color='#1E293B'),
    hovertemplate='<b>%{label}</b><br>Players: %{value:,d}<br>Share: %{percent}<extra></extra>',
    showlegend=False,
), row=2, col=3)
trace_map['donut'] = t
t += 1

# ── Row 3: Retention heatmap ──────────────────────────────────────────────────
hm = hm_data['all']
fig.add_trace(go.Heatmap(
    z=hm['z'], x=['D1', 'D7', 'D30'], y=hm['y'],
    colorscale='Greens',
    text=hm['text'], texttemplate='%{text}',
    textfont=dict(size=9),
    zmin=5, zmax=70,
    colorbar=dict(
        len=0.28, thickness=12,
        x=0.472, xanchor='right', xpad=3,
        y=0.45, yanchor='middle',
        tickfont=dict(size=9, color='#64748B'),
        title=dict(text='%', side='top', font=dict(size=10, color='#64748B')),
    ),
), row=3, col=1)
trace_map['heatmap'] = t
t += 1
fig.update_yaxes(autorange='reversed', row=3, col=1)

# ── Row 3: LTV curves ─────────────────────────────────────────────────────────
trace_map['ltv_bands'] = {}
trace_map['ltv_lines'] = {}
legend_seen = set()
for seg in SEGS:
    sub = ltv_stats[ltv_stats['segment'] == seg].sort_values('day')
    if sub.empty:
        continue
    clr = SEG_CLR[seg]
    x_b = sub['day'].tolist() + sub['day'].tolist()[::-1]
    y_b = sub['p75'].tolist() + sub['p25'].tolist()[::-1]
    fig.add_trace(go.Scatter(
        x=x_b, y=y_b, fill='toself', fillcolor=hex_rgba(clr, 0.12),
        line=dict(width=0), hoverinfo='skip',
        showlegend=False, legendgroup=seg,
    ), row=3, col=3)
    trace_map['ltv_bands'][seg] = t; t += 1

    fig.add_trace(go.Scatter(
        x=sub['day'], y=sub['median'],
        mode='lines+markers', name=seg,
        line=dict(color=clr, width=2.5),
        marker=dict(size=5, color=clr),
        legendgroup=seg,
        showlegend=(seg not in legend_seen),
        hovertemplate=f'<b>{seg}</b><br>Day %{{x}}<br>Median LTV: €%{{y:.2f}}<extra></extra>',
    ), row=3, col=3)
    trace_map['ltv_lines'][seg] = t; t += 1
    legend_seen.add(seg)

# ── Row 4: RFM scatter ────────────────────────────────────────────────────────
trace_map['scatter'] = {}
for seg in reversed(SEGS):  # render lowest-value segments first so Champions draws on top
    sub = rfm_raw[rfm_raw['segment'] == seg]
    if sub.empty:
        continue
    fig.add_trace(go.Scatter(
        x=sub['recency'], y=sub['mc'],
        mode='markers',
        marker=dict(
            size=sub['sz'],
            color=SEG_CLR[seg],
            opacity=0.55,
            line=dict(width=0.5, color='white'),
        ),
        name=seg, legendgroup=seg, showlegend=False,
        hovertemplate=(
            f'<b>{seg}</b><br>'
            'Recency: %{x}d<br>GGR: €%{y:.2f}<br>Sessions: %{text}'
            '<extra></extra>'
        ),
        text=sub['frequency'].astype(str),
    ), row=4, col=1)
    trace_map['scatter'][seg] = t; t += 1

# ── Row 4: D7 metrics by LTV tier ─────────────────────────────────────────────
# Normalize each metric to Low LTV = 1.0 so all three fit on the same axis
d7_metrics = ['avg_bets_d7', 'avg_sessions_d7', 'avg_deposits_d7']
d7_labels  = ['Avg Bets D7', 'Avg Sessions D7', 'Avg Deposits D7']
d7_colors  = ['#F59E0B', '#3B82F6', '#059669']
low_vals = tier_f[tier_f['ltv_tier'] == 'Low'].iloc[0]
for m in d7_metrics:
    tier_f[f'{m}_ix'] = (tier_f[m] / low_vals[m]).round(3)
for metric, label, clr in zip(d7_metrics, d7_labels, d7_colors):
    ix_col = f'{metric}_ix'
    fig.add_trace(go.Bar(
        y=tier_f['ltv_tier'], x=tier_f[ix_col],
        orientation='h', name=label,
        marker=dict(color=clr, opacity=0.8, line=dict(width=0)),
        text=[f'{v:.1f}' for v in tier_f[metric]],
        textposition='outside',
        textfont=dict(color='#374151', size=10),
        hovertemplate=f'<b>%{{y}} LTV</b><br>{label}: %{{text}} (×%{{x:.2f}} vs Low)<extra></extra>',
        legend='legend2',
    ), row=4, col=3)
    t += 1

# ── Layout ────────────────────────────────────────────────────────────────────
fig.update_layout(
    paper_bgcolor='#FFFFFF',
    plot_bgcolor='#F8FAFC',
    font=dict(color='#1E293B', family='Inter, ui-sans-serif, system-ui, sans-serif', size=11),
    height=1500,
    margin=dict(l=50, r=50, t=40, b=50),
    legend=dict(
        bgcolor='rgba(255,255,255,0.95)',
        bordercolor='#E2E8F0',
        borderwidth=1,
        x=0.537, y=0.568,
        xanchor='left', yanchor='top',
        font=dict(size=10, color='#374151'),
        title=dict(text='Segment', font=dict(size=11, color='#94A3B8')),
    ),
    legend2=dict(
        bgcolor='rgba(255,255,255,0.95)',
        bordercolor='#E2E8F0',
        borderwidth=1,
        x=0.99, y=0.24,
        xanchor='right', yanchor='top',
        font=dict(size=10, color='#374151'),
    ),
    barmode='group',
    title=None,
)

axis_kw = dict(
    gridcolor='#F1F5F9',
    linecolor='#E2E8F0',
    zerolinecolor='#E2E8F0',
    tickfont=dict(color='#94A3B8', size=9),
    title_font=dict(color='#64748B', size=10),
)
fig.update_xaxes(**axis_kw)
fig.update_yaxes(**axis_kw)

fig.update_yaxes(title_text='GGR (€)',                     row=2, col=1)
fig.update_xaxes(title_text='Days Since Signup',           row=3, col=3)
fig.update_yaxes(title_text='Cumulative GGR (€)',          row=3, col=3)
fig.update_xaxes(title_text='Recency (days since last bet)',row=4, col=1)
fig.update_yaxes(title_text='Total GGR (€)',               row=4, col=1)
fig.update_xaxes(title_text='Index vs Low LTV (1.0 = baseline)', range=[0, 2.8], row=4, col=3)
fig.update_xaxes(autorange='reversed', row=4, col=1)

fig.update_annotations(font=dict(color='#475569', size=12))

# ── Build HTML with filter bar ────────────────────────────────────────────────
fig_div = fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='casino-dash')

# Segment button HTML
seg_btns_html = '\n'.join(
    f'<button class="seg-btn" data-seg="{seg}" style="--c:{clr}" '
    f'onclick="toggleSeg(this)">{seg}</button>'
    for seg, clr in SEG_CLR.items()
)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LuckyEdge Casino Analytics</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,system-ui,sans-serif;background:#F1F5F9;color:#1E293B}}

/* Header */
.hdr{{
  background:linear-gradient(135deg,#1E3A5F 0%,#1D4ED8 100%);
  padding:20px 36px;
  display:flex;align-items:flex-end;justify-content:space-between;
  box-shadow:0 2px 12px rgba(29,78,216,.3);
}}
.hdr-left h1{{font-size:21px;font-weight:700;color:#fff;letter-spacing:-.3px}}
.hdr-left p{{font-size:12.5px;color:rgba(255,255,255,.6);margin-top:3px}}
.hdr-badge{{
  background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);
  border-radius:20px;padding:5px 14px;font-size:12px;color:rgba(255,255,255,.75);
}}

/* Filter bar */
.filters{{
  background:#fff;border-bottom:1px solid #E2E8F0;
  padding:9px 36px;display:flex;align-items:center;gap:18px;
  position:sticky;top:0;z-index:100;flex-wrap:wrap;
  box-shadow:0 1px 4px rgba(0,0,0,.06);
}}
.fl{{font-size:10.5px;font-weight:600;color:#94A3B8;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}}
.fg{{display:flex;align-items:center;gap:5px}}
.sep{{width:1px;height:22px;background:#E2E8F0;flex-shrink:0}}

/* Generic toggle buttons */
.btn{{
  border:1.5px solid #E2E8F0;background:#fff;border-radius:6px;
  padding:4px 11px;font-size:12px;font-family:inherit;font-weight:500;
  cursor:pointer;transition:all .15s;color:#475569;white-space:nowrap;
}}
.btn:hover{{border-color:#CBD5E1;background:#F8FAFC}}
.btn.on{{background:#1E293B;border-color:#1E293B;color:#fff}}

/* Segment buttons — use CSS custom property --c for per-segment color */
.seg-btn{{
  border:1.5px solid #E2E8F0;background:#fff;border-radius:6px;
  padding:4px 11px;font-size:12px;font-family:inherit;font-weight:500;
  cursor:pointer;transition:all .15s;color:#475569;white-space:nowrap;
}}
.seg-btn:hover{{border-color:var(--c);color:var(--c)}}
.seg-btn.on{{background:var(--c);border-color:var(--c);color:#fff}}

.count-badge{{
  font-size:10px;background:#DBEAFE;color:#1D4ED8;
  border-radius:10px;padding:1px 7px;font-weight:600;display:none;
}}
.count-badge.show{{display:inline-block}}

.reset-btn{{
  border:1.5px solid #E2E8F0;background:#fff;border-radius:6px;
  padding:4px 10px;font-size:11px;font-family:inherit;
  cursor:pointer;color:#94A3B8;transition:all .15s;
}}
.reset-btn:hover{{color:#475569;border-color:#CBD5E1}}

/* Chart card */
.card{{
  background:#fff;margin:16px 24px;border-radius:12px;
  border:1px solid #E2E8F0;overflow:hidden;
  box-shadow:0 1px 4px rgba(0,0,0,.05);
}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-left">
    <h1>LuckyEdge Casino &mdash; Player Analytics Dashboard</h1>
    <p>Cohort window: {date_min} &ndash; {date_max} &nbsp;&middot;&nbsp; 5,000 synthetic players</p>
  </div>
  <div class="hdr-badge">Python &amp; Plotly</div>
</div>

<div class="filters">
  <div class="fg">
    <span class="fl">Segment</span>
    <button class="btn on" id="seg-all" onclick="segAll()">All</button>
    {seg_btns_html}
    <span class="count-badge" id="seg-count"></span>
  </div>
  <div class="sep"></div>
  <div class="fg">
    <span class="fl">Cohort year</span>
    <button class="btn on" data-year="all"  onclick="filterYear(this)">All years</button>
    <button class="btn"    data-year="2023" onclick="filterYear(this)">2023</button>
    <button class="btn"    data-year="2024" onclick="filterYear(this)">2024</button>
  </div>
  <div class="sep"></div>
  <button class="reset-btn" onclick="resetAll()">&#x21BA;&nbsp;Reset</button>
</div>

<div class="card">
{fig_div}
</div>

<script>
const D          = 'casino-dash';
const TMAP       = {json.dumps(trace_map)};
const HMDAT      = {json.dumps(hm_data)};
const KPIS       = {json.dumps(kpi_data)};
const ALL_SEGS   = {json.dumps(SEGS)};
const KPI_GRID   = {json.dumps(kpi_grid)};
const CHART_DATA = {json.dumps(chart_data)};

let activeSeg   = new Set(ALL_SEGS);
let currentYear = 'all';

/* ── KPI helpers ── */
function computeKPIs() {{
  if (activeSeg.size === ALL_SEGS.length) {{
    return KPIS[currentYear];
  }}
  let total_players = 0, total_ggr = 0, weighted_d30 = 0;
  for (const seg of activeSeg) {{
    const k = KPI_GRID[currentYear][seg];
    if (!k) continue;
    total_players += k.total_players;
    total_ggr     += k.total_ggr;
    weighted_d30  += k.avg_d30 * k.total_players;
  }}
  return {{
    total_players,
    total_ggr: Math.round(total_ggr * 100) / 100,
    avg_ltv:   total_players > 0 ? Math.round(total_ggr / total_players * 100) / 100 : 0,
    avg_d30:   total_players > 0 ? Math.round(weighted_d30 / total_players * 10) / 10 : 0,
  }};
}}

function updateKPIs() {{
  const kp = computeKPIs();
  Plotly.restyle(D, {{value: [kp.total_players]}}, [0]);
  Plotly.restyle(D, {{value: [kp.total_ggr]    }}, [1]);
  Plotly.restyle(D, {{value: [kp.avg_ltv]      }}, [2]);
  Plotly.restyle(D, {{value: [kp.avg_d30]      }}, [3]);
}}

/* ── Chart helpers ── */
function updateCharts() {{
  const cd = CHART_DATA[currentYear];

  for (const seg of ALL_SEGS) {{
    const show = activeSeg.has(seg);
    const li = TMAP.ltv_lines[seg], bi = TMAP.ltv_bands[seg];
    if (li !== undefined) {{
      const ld = cd.ltv_lines[seg];
      Plotly.restyle(D, {{x: [ld ? ld.x : []], y: [ld ? ld.y : []], visible: show && !!ld}}, [li]);
    }}
    if (bi !== undefined) {{
      const bd = cd.ltv_bands[seg];
      Plotly.restyle(D, {{x: [bd ? bd.x : []], y: [bd ? bd.y : []], visible: show && !!bd}}, [bi]);
    }}
    const si = TMAP.scatter[seg];
    if (si !== undefined) {{
      const sd = cd.scatter[seg];
      Plotly.restyle(D, {{
        x: [sd ? sd.x : []], y: [sd ? sd.y : []],
        'marker.size': [sd ? sd.sz : []], text: [sd ? sd.text : []],
        visible: show && !!sd,
      }}, [si]);
    }}
  }}

  const dLabels = [], dValues = [];
  for (const seg of ALL_SEGS) {{
    if (activeSeg.has(seg) && cd.donut[seg] !== undefined) {{
      dLabels.push(seg); dValues.push(cd.donut[seg]);
    }}
  }}
  Plotly.restyle(D, {{labels: [dLabels], values: [dValues]}}, [TMAP.donut]);

  if (TMAP.ggr_bar !== undefined && cd.ggr_bar) {{
    const gb = cd.ggr_bar;
    Plotly.restyle(D, {{
      x: [gb.x], y: [gb.y], text: [gb.text], 'marker.color': [gb.colors],
    }}, [TMAP.ggr_bar]);
  }}
}}

/* ── Combined apply ── */
function applyFilters() {{
  updateKPIs();
  updateCharts();
}}

/* ── Segment slicer ── */
function toggleSeg(btn) {{
  const seg = btn.dataset.seg;
  const wasAll = document.getElementById('seg-all').classList.contains('on');
  if (wasAll) {{
    document.getElementById('seg-all').classList.remove('on');
    activeSeg.clear();
    document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('on'));
  }}
  btn.classList.toggle('on');
  if (btn.classList.contains('on')) activeSeg.add(seg);
  else activeSeg.delete(seg);
  if (activeSeg.size === 0) {{ segAll(); return; }}
  updateBadge();
  applyFilters();
}}

function segAll() {{
  activeSeg = new Set(ALL_SEGS);
  document.getElementById('seg-all').classList.add('on');
  document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('on'));
  document.getElementById('seg-count').classList.remove('show');
  applyFilters();
}}

function updateBadge() {{
  const el = document.getElementById('seg-count');
  if (activeSeg.size < ALL_SEGS.length) {{
    el.textContent = activeSeg.size + ' / ' + ALL_SEGS.length;
    el.classList.add('show');
  }} else {{
    el.classList.remove('show');
  }}
}}

/* ── Year slicer ── */
function filterYear(btn) {{
  document.querySelectorAll('[data-year]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  currentYear = btn.dataset.year;
  const hm = HMDAT[currentYear];
  Plotly.restyle(D, {{z: [hm.z], y: [hm.y], text: [hm.text]}}, [TMAP.heatmap]);
  applyFilters();
}}

/* ── Reset ── */
function resetAll() {{
  activeSeg   = new Set(ALL_SEGS);
  currentYear = 'all';
  document.getElementById('seg-all').classList.add('on');
  document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('on'));
  document.getElementById('seg-count').classList.remove('show');
  document.querySelectorAll('[data-year]').forEach(b => b.classList.remove('on'));
  document.querySelector('[data-year="all"]').classList.add('on');
  const hm = HMDAT['all'];
  Plotly.restyle(D, {{z: [hm.z], y: [hm.y], text: [hm.text]}}, [TMAP.heatmap]);
  applyFilters();
}}
</script>
</body>
</html>"""

# WARNING: docs/dashboard.html has been manually enhanced beyond this generated output
# (dark mode toggle, URL state, chip-style filter bar, bug fixes).
# Re-running this script will overwrite those enhancements.
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)

size_kb = OUT.stat().st_size / 1024
print(f'Saved: {OUT}')
print(f'File size: {size_kb:.1f} KB ({size_kb/1024:.2f} MB)')
