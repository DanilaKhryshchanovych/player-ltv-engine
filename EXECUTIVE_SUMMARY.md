# Executive Memo: Player Lifetime Value Analysis

**To:** Head of CRM / VP Product  
**From:** Data Analytics  
**Date:** November 2024  
**Re:** LTV Segmentation & Retention Findings — Jan 2023–Oct 2024 Cohorts  

---

## Summary
The top 20% of players generate 81.1% of all 90-day GGR ($117,260 of $144,636 total), while average D30 retention of 15.9% lags the best-observed cohort by 5 percentage points. Crypto-channel players convert at 74.1% and deliver a median 90-day LTV 2.4× higher than bank-transfer players ($11.94 vs $5.03). The fastest-payoff action is shifting marginal acquisition budget toward crypto and deploying a D7 bet-size trigger for players whose first-week average bet falls below $0.50.

---

## Findings

### Finding 1 — Revenue Concentration
**81.1% of 90-day GGR ($117,260 of $144,636) comes from the top 20% of players** (n = 1,000; avg LTV $117.26). The middle 30% (n = 1,500) averaged $16.32 LTV and contributed ~17% of revenue. The bottom 50% averaged $1.16 LTV and contributed under 2% of revenue — protecting and expanding the top quintile is the dominant value driver.

### Finding 2 — Retention Drop-Off
**Average retention falls from 57.0% (D1) → 39.4% (D7) → 15.9% (D30)** across 21 full cohorts. The best D30 result was 20.85% (April 2024); the worst was 11.86% (January 2023). The D7–D30 window is where approximately 60% of active players churn, making it the highest-leverage intervention zone for CRM.

### Finding 3 — Early Behavioral Signals
**High-LTV players average 3.0× the bet size of Low-LTV players within the first 7 days ($1.28 vs $0.42)** and place 2.1× more total bets (193.5 vs 93.77). Bet size is the sharpest discriminator and is observable by end of day 7, enabling same-week segmentation and targeting before the critical D7–D30 drop.

### Finding 4 — Channel ROI
**Crypto-channel players generate a median 90-day LTV of $11.94** — 2.4× the bank-transfer median ($5.03) — at the highest conversion rate in the dataset (74.1% vs 54.4% for bank transfer; conversion defined as completing a first deposit within 30 days of registration). Despite representing 10% of players, crypto accounts for 19% of total GGR ($27,495 of $144,636), nearly double its volume share.

---

## Segmentation Limitation

The RFM model used to label behavioral segments achieves **33.3% blended accuracy** against ground-truth labels — with the Champions segment (highest-value players) classified correctly only **18.2% of the time**, below chance for a 5-class model. This means individual-level RFM labels (Champions, Loyal, Promising, etc.) are not reliable enough for direct CRM targeting.

**What this affects:** Any workflow that routes individual players by their RFM label (e.g., "send offer X to all Champions") carries high misclassification risk.

**What this does not affect:** Findings 1–4 are derived from raw LTV and behavioral data, not from RFM labels. The D7 bet-size trigger in Recommendation 2 uses directly observed first-week behavior ($0.50 avg bet, 100 total bets), which does not depend on the RFM model's accuracy. Recommendation 1 (channel mix) is similarly grounded in raw GGR per channel.

**Recommended next step:** Replace or augment RFM quintile scoring with a supervised LTV-tier classifier trained on the D7 behavioral signals from Finding 3 before deploying segment-based offers at scale.

---

## Recommendations

| Priority | Action | Expected Impact |
|----------|--------|-----------------|
| 1 | Reallocate 15% of acquisition budget from bank-transfer channel to crypto | Median new-player LTV on incremental cohort rises from ~$7.50 (blended) to ~$11.94 (+59% lift) |
| 2 | Trigger a targeted bonus offer at D7 for players with avg bet <$0.50 and total bets <100 in days 1–7 | If 10% of 1,500 Mid-LTV players shift to High-LTV trajectory, incremental 90-day GGR ≈ +$15,141 (($117.26 − $16.32) × 150) |
| 3 | Deploy a D7 dormancy alert (free spin bundle) for all players with no session logged in the prior 48 hours | Closing the D30 retention gap from 15.9% to 20.85% (April 2024 best) adds ~12 retained players per monthly cohort |

---

## Methodology Note
- Dataset: 5,000 players; 22 months of acquisition data (January 2023 – October 2024); 21 cohorts with complete 90-day LTV windows (January 2023 – September 2024 — October 2024 cohort excluded as its 90-day window extends to January 2025, beyond the data cutoff)
- LTV definition: gross gaming revenue (GGR) in the 90 days following a player's first deposit
- Segmentation: RFM quintile scoring (Recency, Frequency, Monetary) validated against ground-truth behavioral labels — 33.3% blended accuracy (Hibernating 75.9%, At Risk 56.4%, Champions 18.2%, Loyal 9.4%, Promising 4.1%)
- Tools: DuckDB (SQL), Python (pandas, seaborn), Plotly (interactive dashboard)
- Full analysis available in the project repository
