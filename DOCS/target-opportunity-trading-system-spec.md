# Target Opportunity Trading System Spec

Created: 2026-06-05

Purpose: combine the research into one concrete target system: a signal and alert system that identifies risk-adjusted, explainable trading/investing opportunities.

This is system design and research, not investment advice.

---

## 1. Final system goal

The system should not be a pure price predictor.

The better goal is:

```text
Find positive-expected-value opportunities where price is far from fair value,
risk is controlled, timing is improving, and the reason is explainable.
```

In plain English:

```text
Tell me when something is worth attention because the market price,
fair value, probability, risk, and timing are unusually attractive together.
```

The system should answer:

1. What is this asset worth?
2. How far is current price from fair value?
3. Is the target believable?
4. Is there evidence the gap may close?
5. What is the downside if wrong?
6. Is the signal strong enough after risk, liquidity, and costs?
7. Why did the alert fire?
8. What would invalidate the signal?

The core philosophy:

```text
Target price is not the signal.

Target price + uncertainty band + expected value + timing + risk control
= actionable opportunity signal.
```

---

## 2. System name

Suggested name:

```text
Target Opportunity Monitor
```

Shorter internal name:

```text
TOM
```

What TOM does:

```text
For each asset, estimate fair value, expected return, confidence,
timing quality, risk, and alert priority.
```

What TOM does not do in V1:

- It does not automatically execute trades.
- It does not try to predict exact next-day price.
- It does not output a blind buy/sell command.
- It does not trust one model score without explanation.

---

## 3. Highest-level architecture

```text
Data ingestion
  -> Data quality and universe filter
  -> Feature and signal engine
  -> Fair-value / target-price engine
  -> Expected-value engine
  -> Timing and catalyst engine
  -> Risk, liquidity, and uncertainty engine
  -> Portfolio context engine
  -> Alert engine
  -> Explanation and audit layer
  -> Validation and monitoring layer
```

The important separation:

```text
Valuation creates the target.
Quality/growth/revisions decide whether the target is believable.
Momentum/sentiment/catalysts decide whether timing is good.
Volatility/liquidity/dispersion decide how wide the safety band must be.
Expected value decides whether the opportunity is worth attention.
Validation decides whether the signal deserves to exist.
```

---

## 4. Main system outputs

### 4.1 Asset-level output

For every ticker:

```yaml
ticker: ABC
asset_type: equity
currency: USD
current_price: 80.00
base_target_price: 105.00
target_low: 95.00
target_high: 115.00
upside_to_base: 31.25%
upside_to_low: 18.75%
downside_risk_estimate: -15.00%
expected_return_score: 78
expected_value_score: 74
confidence_score: 71
timing_score: 66
risk_score: 58
liquidity_score: 84
opportunity_score: 73
alert_type: bullish_divergence
alert_priority: high
time_horizon: 3-12 months
main_reasons:
  - cheap versus peers and own history
  - upward EPS revisions
  - improving 6-month relative momentum
  - positive post-earnings sentiment
main_risks:
  - high estimate dispersion
  - earnings in 9 days
  - valuation sensitive to margin assumptions
invalidation:
  - EPS revisions turn negative
  - price breaks below risk level
  - fair value estimate falls below 90
data_freshness:
  price: same_day
  fundamentals: latest_quarter
  estimates: 2_days_old
  news: same_day
```

### 4.2 Watchlist output

Ranked list:

```text
Ticker | Price | Target Range | Upside | EV Score | Confidence | Timing | Risk | Alert
ABC    | 80.00 | 95-115       | +31%   | 74       | 71         | 66     | Med  | Bullish divergence
XYZ    | 42.00 | 35-39        | -12%   | 68       | 65         | 72     | Med  | Bearish overvaluation
DEF    | 22.50 | 24-31        | +22%   | 55       | 44         | 76     | High | Watch only
```

### 4.3 Alert output

Every alert should include:

```text
Ticker
Direction
Current price
Fair-value range
Upside/downside
Required gap
Opportunity score
Confidence score
Timing score
Main reasons
Main risks
Invalidation condition
Data freshness
Suggested action category
```

Suggested action categories:

```text
watch
research_deeper
high_priority_review
existing_position_review
risk_warning
ignore_due_to_low_confidence
```

Avoid outputting:

```text
BUY NOW
SELL NOW
GUARANTEED PROFIT
```

The system is an attention and decision-support engine, not an oracle.

---

## 5. Input universe

### 5.1 Asset universe

V1 should probably focus on:

- US large and mid-cap equities
- Liquid ETFs
- Existing personal watchlist
- Existing holdings

Later expansion:

- Canada-listed equities and ETFs
- ADRs
- Sector ETFs
- Crypto
- Prediction markets
- Options overlays

### 5.2 Universe eligibility filters

Minimum filters:

```text
market cap >= chosen threshold
average dollar volume >= chosen threshold
price is not stale
not recently delisted
enough historical price data
latest fundamentals available
sector/industry classification available
```

Purpose:

- Avoid illiquid names.
- Avoid broken data.
- Avoid alerts on stale prices.
- Avoid false backtest performance from survivorship bias.

---

## 6. Full input catalog

### 6.1 Market data inputs

Raw data:

- Open
- High
- Low
- Close
- Adjusted close
- Volume
- VWAP if available
- Bid/ask spread if available
- Corporate actions
- Splits
- Dividends
- Trading halts
- Exchange
- Currency

Derived features:

- Daily returns
- Weekly returns
- Monthly returns
- 1-month return
- 3-month return
- 6-month return
- 12-month return excluding latest month
- Drawdown from 52-week high
- Distance to 52-week high
- Moving average slopes
- Relative strength versus sector
- Relative strength versus benchmark
- Realized volatility
- Beta
- Idiosyncratic volatility
- Average dollar volume
- Turnover
- Volume spike
- Price-volume confirmation

System use:

- Momentum score
- Reversal score
- Volatility score
- Liquidity score
- Alert threshold adjustment

---

### 6.2 Fundamental inputs

Raw financial statement fields:

- Revenue
- Gross profit
- Operating income
- EBITDA
- EBIT
- Net income
- EPS
- Diluted EPS
- Cash flow from operations
- Capital expenditure
- Free cash flow
- Cash
- Short-term investments
- Debt
- Net debt
- Assets
- Equity
- Book value
- Tangible book value
- Shares outstanding
- Diluted shares
- Dividends
- Buybacks
- Share-based compensation
- Working capital
- Inventory
- Receivables
- Payables

Derived features:

- Revenue growth
- EPS growth
- EBITDA growth
- FCF growth
- Gross margin
- Operating margin
- Net margin
- FCF margin
- ROE
- ROA
- ROIC
- Gross profit / assets
- Cash conversion
- CFO / net income
- Accruals
- Net debt / EBITDA
- Debt / equity
- Interest coverage
- Current ratio
- Quick ratio
- Share count growth
- Buyback yield
- Dividend yield
- Shareholder yield

System use:

- Quality score
- Growth score
- Financial strength score
- Valuation assumptions
- Confidence score
- Risk score

---

### 6.3 Valuation inputs

Raw data:

- Price
- Market cap
- Enterprise value
- Earnings
- Forward EPS
- Revenue
- Forward revenue
- EBITDA
- Forward EBITDA
- EBIT
- FCF
- Book value
- Tangible book
- Net cash/debt
- Peer group multiples
- Historical own multiples
- Analyst target prices if available
- Discount rate assumptions
- Long-term growth assumptions
- Terminal multiple assumptions

Derived valuation metrics:

- Trailing P/E
- Forward P/E
- PEG
- EV/Revenue
- EV/EBITDA
- EV/EBIT
- Price/book
- Price/tangible book
- Price/FCF
- Earnings yield
- FCF yield
- Dividend yield
- Shareholder yield
- EV/gross profit
- Sector-relative valuation percentile
- Own-history valuation percentile
- Reverse DCF implied growth
- Reverse DCF implied margin
- Target price from peer multiples
- Target price from historical multiples
- Target price from DCF
- Target price from analyst consensus adjusted for lag/dispersion

System use:

- Main fair-value engine
- Target range construction
- Overvaluation/undervaluation signal

---

### 6.4 Analyst estimate and revision inputs

Raw data:

- Consensus EPS
- Consensus revenue
- Consensus EBITDA
- Consensus FCF
- Estimate dates
- Number of analysts
- Analyst target prices
- Analyst ratings
- Recommendation changes
- Guidance
- Reported earnings
- Reported revenue

Derived features:

- EPS revision 1 month
- EPS revision 3 months
- Revenue revision 1 month
- Revenue revision 3 months
- EBITDA revision
- FCF revision
- Revision breadth
- Up revision count
- Down revision count
- Recommendation upgrade/downgrade
- Target price revision
- Consensus target upside
- Target price dispersion
- Estimate dispersion
- Earnings surprise
- Revenue surprise
- Guidance surprise
- Standardized unexpected earnings
- Post-earnings announcement drift score

System use:

- Growth expectations
- Target adjustment
- Confidence adjustment
- Timing score
- Catalyst score

---

### 6.5 News, sentiment, and text inputs

Raw data:

- News headlines
- Full news articles
- Press releases
- SEC filings
- Earnings call transcripts
- Management prepared remarks
- Q&A transcripts
- Analyst note summaries if licensed
- Social media posts
- Reddit posts/comments
- X/Twitter posts if available through API/vendor
- StockTwits messages
- Search interest
- Mention counts
- Source credibility
- Timestamp

Derived features:

- News sentiment
- News volume
- News novelty
- News relevance
- Event type
- Earnings call tone
- Tone change versus previous calls
- Negative language increase
- Risk language increase in filings
- Social bullish/bearish score
- Social mention velocity
- Social attention spike
- Topic sentiment
- Influencer/source-weighted sentiment
- Bot/spam-adjusted sentiment
- Sentiment disagreement

System use:

- Sentiment score
- Timing score
- Catalyst identification
- Risk warnings
- Explanation layer

Important caution:

Sentiment is usually noisy. It should rarely create a target price by itself. It is more useful as a timing and confirmation layer.

---

### 6.6 Catalyst and event inputs

Raw data:

- Earnings calendar
- Ex-dividend dates
- Investor day dates
- Product launch dates
- Regulatory dates
- FDA/PDUFA dates for biotech
- Court dates
- Macro data release dates
- Central bank meetings
- Index rebalance dates
- Lockup expiration dates
- Debt maturity dates
- M&A announcements
- Buyback announcements
- Dividend changes
- Activist announcements

Derived features:

- Days to earnings
- Days after earnings
- Earnings surprise event flag
- Guidance change event flag
- Product launch proximity
- Regulatory binary event risk
- Investor day catalyst
- Index inclusion/deletion pressure
- Lockup expiration risk
- Buyback support
- Dividend cut/increase signal
- Activist pressure signal

System use:

- Timing score
- Event risk adjustment
- Alert urgency
- Invalidation logic

---

### 6.7 Macro, sector, and regime inputs

Raw data:

- Benchmark index returns
- Sector ETF returns
- Factor ETF returns
- Interest rates
- Yield curve
- Inflation
- CPI/PCE surprise
- Unemployment
- PMI/ISM
- GDP nowcasts
- Credit spreads
- VIX
- Dollar index
- Oil
- Commodities
- Market breadth

Derived features:

- Risk-on/risk-off regime
- Rate regime
- Inflation regime
- Credit stress regime
- Volatility regime
- Sector momentum
- Sector breadth
- Factor momentum
- Value/growth regime
- Quality/low-vol defensive regime
- Market trend filter

System use:

- Factor weight adjustment
- Sector-relative normalization
- Alert threshold adjustment
- Portfolio risk context

---

### 6.8 Positioning, ownership, and flows inputs

Raw data:

- Insider purchases/sales
- Insider ownership
- Institutional ownership
- 13F changes
- Short interest
- Borrow fee
- Days to cover
- ETF holdings
- ETF flows
- Mutual fund flows
- Share issuance
- Buyback execution
- Option open interest if available

Derived features:

- Insider purchase cluster
- Insider sale cluster
- Insider trade size relative to holdings
- Short interest / float
- Short interest change
- Borrow fee change
- Crowded long risk
- Crowded short risk
- ETF flow pressure
- Fund flow pressure
- Index rebalance flow pressure
- Secondary offering risk

System use:

- Timing score
- Squeeze/crowding warning
- Risk score
- Explanation layer

---

### 6.9 Options-implied inputs

Raw data:

- Implied volatility
- Realized volatility
- Option volume
- Option open interest
- Put/call volume
- Put/call open interest
- Skew
- Term structure
- Expiry calendar
- Strike-level data

Derived features:

- IV rank
- IV percentile
- IV minus realized volatility
- Put skew
- Call skew
- Risk reversal
- Put/call ratio
- Option volume imbalance
- Unusual options activity
- Implied earnings move
- Implied probability distribution
- Volatility crush risk

System use:

- Risk band
- Event risk
- Market-implied uncertainty
- Timing clue

V1 note:

Options data can be expensive and noisy. It is useful, but should probably be V2 unless the data is already available.

---

### 6.10 Alternative data inputs

Potential data:

- Web traffic
- App downloads
- App active users
- Search trends
- Credit/debit card transactions
- Email receipt panels
- Geolocation/foot traffic
- Satellite imagery
- Job postings
- Product prices
- Reviews and ratings
- Shipping/import data
- Patent filings
- Government contracts
- App rankings
- Ad spend

Derived features:

- Website traffic growth
- App download growth
- Active-user growth
- Search interest acceleration
- Transaction nowcast
- Foot-traffic nowcast
- Review sentiment
- Hiring growth
- Layoff signal
- Product discounting
- Shipment growth
- Patent velocity

System use:

- Fundamental nowcasting
- Growth confirmation
- Early warning before earnings

V1 note:

Alternative data should be optional at first. Use only if you can validate it and track vendor/data drift.

---

### 6.11 Governance, legal, accounting, and ESG risk inputs

Raw data:

- Auditor changes
- Restatements
- Late filings
- Material weakness disclosures
- Related-party transactions
- Insider pledges
- Board composition
- Executive compensation
- Litigation
- Regulatory investigations
- ESG controversies
- Cybersecurity incidents
- Labor disputes

Derived features:

- Accounting risk score
- Fraud/manipulation risk score
- Governance risk score
- Litigation severity score
- Regulatory risk score
- Filing risk language change
- Restatement flag
- Late filing flag

System use:

- Confidence reduction
- Risk score
- Alert suppression
- Watchlist warning

---

### 6.12 Portfolio and user-context inputs

Raw data:

- Current holdings
- Cost basis
- Position size
- Portfolio weights
- Cash balance
- Sector exposure
- Currency exposure
- Account type
- Tax constraints
- Maximum position size
- Maximum sector exposure
- Risk tolerance
- Time horizon
- Preferred assets
- Do-not-trade list

Derived features:

- Existing exposure to ticker
- Existing exposure to sector
- Concentration risk
- Correlation with current holdings
- Portfolio marginal risk
- Position sizing suggestion
- Tax-sensitive alert flag

System use:

- Alert priority
- Position review
- Risk management
- Sizing guidance

Important:

The same signal can mean different things depending on whether you already own it.

Example:

```text
Bullish divergence on a stock you do not own -> research opportunity
Bullish divergence on a stock you already own -> add/hold review
Bearish divergence on a stock you own -> risk review
Bearish divergence on a stock you do not own -> avoid/short-watch only
```

---

## 7. Detailed component design

### 7.1 Component 1: Data ingestion layer

Job:

Collect and timestamp raw data.

Required capabilities:

- Pull prices.
- Pull fundamentals.
- Pull estimates if available.
- Pull news/sentiment if available.
- Pull sector/industry classifications.
- Store raw data unchanged.
- Track data timestamp and source.
- Track effective date versus publish date.

Key rule:

```text
Never confuse fiscal period date with data availability date.
```

This matters because using financial statement data before it was actually published creates look-ahead bias.

---

### 7.2 Component 2: Data quality and universe filter

Job:

Decide whether the ticker is eligible for scoring.

Checks:

- Price is fresh.
- Volume is sufficient.
- No missing key fields.
- Enough history.
- Corporate actions are adjusted.
- Fundamentals are not stale.
- Estimates are not stale.
- Ticker is mapped correctly.
- Currency is known.
- Sector is known.
- Suspensions/halts handled.

Output:

```yaml
eligible: true
data_quality_score: 91
warnings:
  - none
```

If data is bad:

```yaml
eligible: false
reason: stale_price_or_missing_fundamentals
```

This component should be allowed to suppress all downstream alerts.

---

### 7.3 Component 3: Feature and signal engine

Job:

Convert raw inputs into clean, comparable signals.

Standard transformations:

- Winsorize outliers.
- Fill missing values cautiously.
- Standardize by sector.
- Standardize by market-cap bucket.
- Convert to percentile ranks.
- Convert to z-scores.
- Track directionality.
- Track signal age.
- Track missing-rate.
- Track correlation with other signals.

Example signal record:

```yaml
signal_id: valuation.forward_pe_sector_percentile
family: valuation
value: 18.2
sector_percentile: 22
direction: lower_is_better
score: 78
freshness: recent
confidence: medium
```

---

### 7.4 Component 4: Fair-value / target-price engine

Job:

Estimate what the asset is worth.

Sub-models:

1. Peer multiple model
2. Historical own-multiple model
3. DCF/scenario model
4. Reverse DCF reasonableness model
5. Analyst target adjustment model
6. Asset-specific valuation model

Example target blend:

```text
base_target =
  0.30 * peer_multiple_target
  + 0.25 * historical_multiple_target
  + 0.25 * dcf_target
  + 0.10 * reverse_dcf_reasonable_target
  + 0.10 * analyst_target_adjusted
```

The weights should vary by asset type and sector.

Examples:

```text
Stable cash-flow company:
DCF weight higher

Cyclical industrial:
Normalized peer multiple and through-cycle earnings weight higher

Bank:
P/TBV, ROE, CET1, credit quality weight higher

SaaS:
Revenue growth, gross margin, FCF margin, Rule of 40, EV/Sales weight higher

REIT:
NAV, FFO, AFFO, cap rate, occupancy weight higher

Biotech:
Probability-weighted pipeline value, cash runway, binary catalyst risk
```

Output:

```yaml
peer_multiple_target: 103
historical_multiple_target: 98
dcf_target: 118
reverse_dcf_reasonable_target: 107
analyst_target_adjusted: 101
base_target: 106
target_low: 94
target_high: 119
valuation_score: 79
valuation_confidence: 68
```

Key rule:

```text
Output a range, not just one target price.
```

---

### 7.5 Component 5: Quality and fundamentals engine

Job:

Decide whether the business quality supports the target.

Subscores:

- Profitability
- Margin quality
- Cash conversion
- ROIC/ROE
- Balance sheet strength
- Accounting quality
- Business stability
- Capital allocation

Example:

```yaml
quality_score: 74
profitability_score: 81
cash_conversion_score: 69
balance_sheet_score: 77
accounting_quality_score: 63
capital_allocation_score: 70
quality_summary:
  - high ROIC
  - positive FCF conversion
  - moderate leverage
```

System effect:

- Raises/lower confidence.
- Justifies valuation premium/discount.
- Helps avoid value traps.

---

### 7.6 Component 6: Growth and expectation engine

Job:

Estimate whether the future operating path supports the target.

Subscores:

- Historical growth
- Forward expected growth
- Growth acceleration/deceleration
- Margin expansion/contraction
- Unit economics
- Sector-relative growth

Output:

```yaml
growth_score: 67
revenue_growth_score: 72
eps_growth_score: 61
forward_growth_score: 69
growth_acceleration_score: 58
growth_summary:
  - forward revenue estimates rising
  - EPS growth stable
  - margin expansion modest
```

System effect:

- Changes target assumptions.
- Changes confidence.
- Helps distinguish expensive compounder versus overvalued growth story.

---

### 7.7 Component 7: Analyst revision and surprise engine

Job:

Detect whether professional expectations are moving.

Subscores:

- EPS revision
- Revenue revision
- EBITDA/FCF revision
- Revision breadth
- Recommendation change
- Target price revision
- Estimate dispersion
- Earnings surprise
- Guidance surprise
- PEAD score

Output:

```yaml
revision_score: 82
eps_revision_3m: positive
revenue_revision_3m: positive
revision_breadth: broad
estimate_dispersion: medium
surprise_score: 76
summary:
  - EPS consensus up 6% over 3 months
  - revenue consensus up 3%
  - target price revisions positive
```

System effect:

- Strong timing/confirmation signal.
- Can raise target price.
- Can suppress alerts if estimates deteriorate.

---

### 7.8 Component 8: Momentum and price-action engine

Job:

Detect whether price behavior agrees with the thesis.

Subscores:

- Medium-term momentum
- Short-term reversal
- Sector-relative momentum
- Market-relative momentum
- Trend consistency
- Breakout/breakdown
- 52-week high proximity
- Volume confirmation

Output:

```yaml
momentum_score: 64
relative_momentum_score: 71
trend_score: 59
volume_confirmation_score: 62
summary:
  - 6-month sector-relative return positive
  - still below 52-week high
  - volume confirmation moderate
```

System effect:

- Improves timing score.
- Avoids buying cheap stocks with collapsing momentum too early.
- Flags overextended stocks when current price is above target range.

---

### 7.9 Component 9: Sentiment and narrative engine

Job:

Detect whether perception is improving or worsening.

Subscores:

- News sentiment
- News volume
- News novelty
- Earnings call tone
- Filing language change
- Social sentiment
- Social attention velocity
- Topic-specific sentiment
- Source credibility

Output:

```yaml
sentiment_score: 69
news_sentiment_score: 74
social_sentiment_score: 61
attention_score: 78
noise_score: 42
summary:
  - positive news after earnings
  - social attention rising
  - sentiment not yet euphoric
```

System effect:

- Timing and catalyst confirmation.
- Warns when negative news explains the valuation gap.
- Should not be trusted alone.

---

### 7.10 Component 10: Catalyst and timing engine

Job:

Decide whether the opportunity has a reason to move now.

Inputs:

- Earnings dates
- Guidance changes
- Product launches
- Regulatory events
- Buyback/dividend announcements
- Activism
- M&A
- Index changes
- Macro events

Output:

```yaml
catalyst_score: 62
event_risk_score: 55
upcoming_events:
  - earnings in 9 days
  - investor day in 34 days
timing_summary:
  - positive revision trend ahead of investor day
  - earnings event adds short-term risk
```

System effect:

- Raises alert urgency if catalyst is constructive.
- Raises required gap if event risk is binary.
- Helps avoid "cheap but no reason to move" alerts.

---

### 7.11 Component 11: Risk, volatility, and uncertainty engine

Job:

Estimate how much can go wrong and how wide the target band must be.

Subscores:

- Realized volatility
- Downside volatility
- Beta
- Idiosyncratic volatility
- Max drawdown
- Estimate dispersion
- Target price dispersion
- Event risk
- Leverage risk
- Liquidity risk
- Governance/accounting risk

Output:

```yaml
risk_score: 58
volatility_score: 49
balance_sheet_risk_score: 31
dispersion_risk_score: 64
event_risk_score: 57
uncertainty_band: 12.5%
required_gap: 18.0%
summary:
  - volatility above sector median
  - estimate dispersion medium-high
  - liquidity acceptable
```

System effect:

- Creates target range.
- Determines required alert gap.
- Reduces position size suggestion.
- Suppresses alerts when risk is too high.

Example:

```text
Stable mega-cap:
uncertainty band = 8-12%
required gap = 12-18%

Small volatile stock:
uncertainty band = 25-40%
required gap = 30-50%
```

---

### 7.12 Component 12: Liquidity and tradability engine

Job:

Judge whether the signal is actionable.

Subscores:

- Average dollar volume
- Bid/ask spread
- Turnover
- Market cap
- Free float
- Price reliability
- Data freshness

Output:

```yaml
liquidity_score: 84
tradability: good
estimated_slippage_risk: low
summary:
  - high dollar volume
  - tight spread
  - no stale price warning
```

System effect:

- Suppresses illiquid alerts.
- Increases required gap for thinly traded names.
- Adds warning to alert.

---

### 7.13 Component 13: Positioning and flows engine

Job:

Detect ownership pressure and crowdedness.

Subscores:

- Insider activity
- Institutional ownership changes
- Short interest
- Borrow fee
- ETF/fund flow exposure
- Buyback support
- Issuance pressure
- Crowding

Output:

```yaml
positioning_score: 61
insider_score: 73
short_interest_score: 52
flow_score: 58
summary:
  - insider purchases supportive
  - short interest moderate
  - no major ETF flow pressure
```

System effect:

- Timing confirmation.
- Crowding warning.
- Squeeze/forced-selling context.

---

### 7.14 Component 14: Macro, sector, and peer context engine

Job:

Decide whether the broader environment helps or hurts.

Subscores:

- Market regime
- Sector momentum
- Sector breadth
- Factor regime
- Rate sensitivity
- Credit sensitivity
- Commodity sensitivity
- Peer-relative score

Output:

```yaml
macro_score: 56
sector_score: 68
peer_context_score: 74
summary:
  - sector momentum positive
  - stock cheaper than peers with similar growth
  - rate environment neutral-negative
```

System effect:

- Adjusts target confidence.
- Adjusts factor weights.
- Adds context to alert.

---

### 7.15 Component 15: Expected-value engine

Job:

Convert target, probability, downside, cost, and timing into an opportunity estimate.

Core formula:

```text
expected_value =
  probability_up * average_upside
  - probability_down * average_downside
  - estimated_costs
```

For a long opportunity:

```text
average_upside = target_base / current_price - 1
average_downside = current_price / stop_or_invalidation_price - 1
probability_up = calibrated probability price reaches target zone
probability_down = calibrated probability thesis fails
```

A practical V1 approximation:

```text
probability_up = function(confidence_score, timing_score, revision_score, momentum_score)
average_upside = base_target / current_price - 1
average_downside = risk_level_or_invalidation_loss
expected_value_score = rank(expected_value across universe)
```

Output:

```yaml
probability_up_estimate: 57%
average_upside_estimate: 31%
average_downside_estimate: 14%
estimated_costs: 0.4%
expected_value: 10.1%
expected_value_score: 74
```

Important:

The probability estimate must be calibrated and validated over time. Do not pretend it is exact.

---

### 7.16 Component 16: Opportunity score engine

Job:

Combine everything into one ranking score without hiding the parts.

Recommended formula:

```text
opportunity_score =
  0.30 * expected_value_score
  + 0.20 * valuation_gap_score
  + 0.15 * confidence_score
  + 0.15 * timing_score
  + 0.10 * liquidity_score
  + 0.10 * risk_adjustment_score
```

Where:

```text
risk_adjustment_score = 100 - risk_penalty_score
```

But keep the components visible. A single score without reasons is dangerous.

Output:

```yaml
opportunity_score: 73
classification: high_priority_review
```

Classification bands:

```text
85-100: exceptional, rare, review immediately
70-84: high priority
55-69: watchlist
40-54: weak/mixed
0-39: ignore or risk warning
```

---

### 7.17 Component 17: Alert engine

Job:

Decide when to notify you.

Bullish alert rule:

```text
current_price < target_low
and upside_to_base >= required_gap
and expected_value_score >= 65
and confidence_score >= 55
and timing_score >= 50
and liquidity_score >= 50
and data_quality_score >= 80
and no hard risk block
```

Bearish alert rule:

```text
current_price > target_high
and downside_to_base <= -required_gap
and negative_revision_or_momentum_confirmation
and confidence_score >= 55
and liquidity_score >= 50
and data_quality_score >= 80
```

Watch-only rule:

```text
large valuation gap
but confidence low
or timing weak
or event risk high
```

Risk-warning rule:

```text
existing position
and fair value falls
or revisions turn negative
or price breaks invalidation level
or risk score worsens sharply
```

Alert types:

```text
bullish_divergence
bearish_overvaluation
watch_only_gap
target_upgrade
target_downgrade
revision_inflection
momentum_confirmation
sentiment_inflection
catalyst_approaching
risk_warning
data_quality_warning
existing_position_review
```

---

### 7.18 Component 18: Explanation and audit layer

Job:

Make every alert understandable and reviewable.

Every alert should include:

```text
What changed?
Why did it alert now?
Which signals contributed most?
Which signals disagree?
What is the biggest risk?
What would invalidate the signal?
How fresh is the data?
What source data was used?
```

Example:

```text
ABC triggered a bullish divergence alert because the current price is 24%
below the lower fair-value band while EPS revisions and sector-relative
momentum improved. The target is supported by peer multiples and historical
valuation. The biggest risk is high estimate dispersion before earnings.
```

Audit log fields:

```yaml
alert_id:
timestamp:
ticker:
alert_type:
input_snapshot_id:
scores:
reasons:
risks:
thresholds:
model_version:
data_versions:
user_action:
future_outcome:
```

This audit log is critical because it lets you learn whether the system is actually useful.

---

### 7.19 Component 19: Portfolio and sizing guidance

Job:

Translate signal quality into risk-aware sizing suggestions.

V1 should provide categories, not automatic orders:

```text
No action
Watch
Research
Small starter position candidate
Add candidate
Reduce/risk review candidate
Exit review candidate
```

Position sizing should consider:

- Portfolio size
- Existing position
- Risk per idea
- Volatility
- Liquidity
- Correlation with portfolio
- Confidence
- Drawdown tolerance
- Event risk

Simple sizing idea:

```text
base_position_weight =
  max_position_weight
  * opportunity_score_factor
  * confidence_factor
  * liquidity_factor
  * volatility_adjustment
  * portfolio_concentration_adjustment
```

Risk-based sizing:

```text
shares =
  allowed_dollar_risk
  / abs(entry_price - invalidation_price)
```

Important:

Position sizing is where a good signal becomes a survivable system. A positive expected-value idea can still destroy the portfolio if sized too large.

---

### 7.20 Component 20: Validation and monitoring layer

Job:

Prove whether signals work and detect when they stop working.

Validation metrics:

- IC
- RankIC
- ICIR
- Hit rate
- Precision at top decile
- Quantile return spread
- Average forward return by score bucket
- Sharpe
- Sortino
- Calmar
- Max drawdown
- Drawdown duration
- Turnover
- Transaction costs
- Slippage estimate
- Capacity
- Coverage
- Missing rate
- Feature drift
- Prediction drift
- Alert precision
- False-positive rate
- Time-to-target
- Time-to-invalidation

Validation rules:

1. Use point-in-time data.
2. Use real publish dates.
3. Avoid survivorship bias.
4. Include transaction costs.
5. Test by sector.
6. Test by market-cap bucket.
7. Test by regime.
8. Test out-of-sample.
9. Run walk-forward validation.
10. Compare to simple baselines.
11. Track live paper results.
12. Kill or downgrade signals that decay.

Key idea:

```text
A signal is not real because it sounds logical.
A signal is real only if it survives clean validation and live monitoring.
```

---

## 8. Score definitions

### 8.1 Valuation gap score

Measures how far price is from fair value.

```text
valuation_gap = base_target / current_price - 1
```

For bullish:

```text
higher positive gap = better
```

For bearish:

```text
larger negative gap = stronger overvaluation signal
```

Must be adjusted by uncertainty:

```text
valuation_gap_score should be high only when current price is outside the fair-value band.
```

---

### 8.2 Confidence score

Measures how believable the target is.

Inputs:

- Quality
- Growth
- Balance sheet
- Cash flow
- Estimate dispersion
- Target model agreement
- Data freshness
- Accounting risk

High confidence example:

```text
multiple valuation models agree
quality is strong
cash flow is real
estimate dispersion is low
data is fresh
```

Low confidence example:

```text
DCF says cheap but peer model says expensive
estimates are stale
target depends on aggressive margin assumptions
business is highly cyclical
```

---

### 8.3 Timing score

Measures whether the gap may close soon.

Inputs:

- Momentum
- Earnings revisions
- News sentiment
- Catalyst proximity
- Sector strength
- Insider/flow support
- Post-earnings drift

High timing example:

```text
upward revisions + improving momentum + positive catalyst
```

Low timing example:

```text
cheap stock with falling estimates and no catalyst
```

---

### 8.4 Risk score

Measures what can go wrong.

Inputs:

- Volatility
- Downside volatility
- Beta
- Leverage
- Liquidity
- Estimate dispersion
- Event risk
- Governance/accounting risk
- Positioning crowding

Risk score should affect:

- Fair-value band width
- Required alert gap
- Position size
- Alert priority

---

### 8.5 Expected-value score

Measures whether the opportunity is attractive after probability and downside.

```text
EV = P(up) * upside - P(down) * downside - costs
```

The goal is not:

```text
highest upside
```

The goal is:

```text
best probability-weighted upside after downside and cost
```

---

### 8.6 Opportunity score

Final ranking score.

Recommended:

```text
opportunity_score =
  expected_value_score
  + valuation_gap_score
  + confidence_score
  + timing_score
  + liquidity_score
  - risk_penalty
```

Do not let one very high subscore dominate everything.

Example:

```text
Huge upside but terrible confidence = watch only.
Great quality but no valuation gap = no alert.
Strong momentum but overvalued = avoid or risk warning.
Cheap and high confidence but no timing = watchlist, not urgent.
Cheap + high confidence + improving timing = alert.
```

---

## 9. Alert logic in detail

### 9.1 Bullish divergence

Meaning:

```text
Market price is below fair value and evidence suggests the gap may close.
```

Trigger:

```text
current_price < target_low
upside_to_base > required_gap
expected_value_score >= 65
confidence_score >= 55
timing_score >= 50
liquidity_score >= 50
```

Example:

```text
Current price: 80
Target range: 95-115
Base target: 105
Upside to base: +31%
Required gap: 18%
Result: bullish divergence alert
```

---

### 9.2 Bearish overvaluation

Meaning:

```text
Market price is above fair value and negative confirmation is present.
```

Trigger:

```text
current_price > target_high
downside_to_base < -required_gap
negative revisions or weakening momentum
confidence_score >= 55
```

Use:

- Review existing long positions.
- Avoid new buys.
- Consider hedge/trim if appropriate.

---

### 9.3 Watch-only valuation gap

Meaning:

```text
Large gap, but not enough confirmation.
```

Examples:

- Cheap but estimates falling.
- Cheap but no catalyst.
- Cheap but sentiment extremely negative for valid reasons.
- Cheap but liquidity poor.
- Cheap but accounting risk high.

Output:

```text
Watch only. Do more research. No high-priority alert.
```

---

### 9.4 Revision inflection

Meaning:

```text
Expectations are changing quickly.
```

Triggers:

- EPS revisions turn from negative to positive.
- Revenue revisions turn positive.
- Guidance raised.
- Target prices revised up.
- Estimate dispersion narrows.

Use:

- Strong timing signal.
- Can upgrade watchlist name to active alert.

---

### 9.5 Momentum confirmation

Meaning:

```text
Price action begins to confirm the valuation thesis.
```

Triggers:

- Sector-relative momentum turns positive.
- 3m/6m momentum improves.
- Breakout with volume.
- Drawdown stops worsening.
- Reclaim key moving average.

Use:

- Helps avoid premature value entries.

---

### 9.6 Sentiment inflection

Meaning:

```text
Narrative is changing.
```

Triggers:

- News sentiment improves.
- Earnings call tone improves.
- Social attention rises without extreme hype.
- Negative narrative fades.
- Positive topic emerges.

Use:

- Timing confirmation.
- Catalyst detection.

---

### 9.7 Risk warning

Meaning:

```text
An existing position or watchlist asset has worsening risk.
```

Triggers:

- Fair value falls.
- EPS revisions turn down.
- Price breaks invalidation level.
- Volatility spikes.
- Liquidity deteriorates.
- Accounting/legal warning appears.
- Event risk rises.

Output:

```text
Review existing position. Thesis may be deteriorating.
```

---

## 10. Invalidation design

Every alert must have an invalidation condition.

Examples:

### Fundamental invalidation

```text
Target price falls below current price.
Revenue/EPS revisions turn negative.
Margins deteriorate beyond assumption.
Debt risk increases.
```

### Price invalidation

```text
Price breaks below risk level.
Momentum deteriorates sharply.
Relative strength turns negative.
```

### Sentiment/catalyst invalidation

```text
Catalyst fails.
Guidance disappoints.
Regulatory decision negative.
News sentiment turns strongly negative.
```

### Data invalidation

```text
Data stale.
Corporate action mismatch.
Missing key financial statement.
Ticker mapping uncertain.
```

This is important because a signal without invalidation can become an emotional long-term bag.

---

## 11. V1 system scope

Build V1 around the highest-value components:

### Required V1 inputs

- Price history
- Adjusted close
- Volume
- Market cap
- Sector/industry
- Financial statements
- Basic valuation ratios
- Forward estimates if available
- Analyst targets/revisions if available
- Earnings calendar
- Basic news sentiment if available
- Current holdings/watchlist if available

### Required V1 components

1. Data quality filter
2. Valuation/target engine
3. Quality score
4. Growth score
5. Revision score
6. Momentum score
7. Risk/volatility/liquidity engine
8. Alert engine
9. Explanation layer
10. Audit log

### V1 output

- Daily watchlist ranking
- Alert report
- Target range per ticker
- Opportunity score
- Reason codes
- Risk codes
- Invalidation condition
- Data freshness status

### V1 should not include yet

- Automatic trade execution
- Complex options signals
- Expensive alternative data
- Overfit ML ensemble
- Unvalidated LLM trading decisions

---

## 12. V2 and V3 expansion

### V2

Add:

- Options-implied signals
- Short interest and borrow fee
- Insider activity
- ETF/fund flows
- Earnings call transcript sentiment
- Filing risk-language changes
- Portfolio-aware sizing
- Walk-forward validation dashboard
- Paper-trading outcome tracking

### V3

Add:

- Alternative data
- Sector-specific KPI models
- Asset-specific valuation modules
- Machine learning rank model
- Probability calibration
- Quantile return forecasts
- Scenario simulator
- Regime-aware factor weighting
- Automated monitoring/notifications

---

## 13. Data model

Suggested tables:

```text
assets
prices
fundamentals
estimates
analyst_targets
news_items
sentiment_scores
events
signals
targets
scores
alerts
alert_reasons
alert_outcomes
portfolio_positions
model_versions
data_quality_checks
```

### assets

```text
ticker
name
asset_type
exchange
currency
sector
industry
country
active_flag
```

### targets

```text
date
ticker
base_target
target_low
target_high
target_method
valuation_model_scores
uncertainty_band
model_version
```

### scores

```text
date
ticker
valuation_gap_score
quality_score
growth_score
revision_score
momentum_score
sentiment_score
catalyst_score
risk_score
liquidity_score
confidence_score
timing_score
expected_value_score
opportunity_score
```

### alerts

```text
alert_id
timestamp
ticker
alert_type
priority
current_price
base_target
target_low
target_high
required_gap
opportunity_score
confidence_score
timing_score
risk_score
status
model_version
```

### alert_outcomes

```text
alert_id
date_5d_return
date_20d_return
date_60d_return
date_120d_return
hit_target_flag
hit_invalidation_flag
max_favorable_excursion
max_adverse_excursion
user_action
notes
```

---

## 14. User interface design

### Main screens

1. Dashboard
2. Watchlist
3. Alerts
4. Ticker detail
5. Portfolio review
6. Signal diagnostics
7. Backtest/validation
8. Data health

### Dashboard cards

- New high-priority alerts
- Existing position warnings
- Top bullish divergences
- Top bearish divergences
- Biggest target changes
- Biggest revision changes
- Data quality warnings

### Ticker detail page

Should show:

- Current price
- Fair-value range
- Target history
- Price versus target chart
- Opportunity score history
- Signal breakdown
- Main reasons
- Main risks
- Invalidation condition
- Source data freshness
- Similar peer comparison
- Past alerts and outcomes

### Alert detail page

Should answer:

```text
Why now?
What changed?
What is the target?
How confident is it?
What is the downside?
What would prove it wrong?
What should I check manually?
```

---

## 15. Example full alert

```text
Alert: Bullish Divergence - High Priority

Ticker: ABC
Current price: 80.00
Base target: 105.00
Fair-value range: 95.00 - 115.00
Upside to base: +31.3%
Upside to lower band: +18.8%
Required alert gap: +18.0%
Time horizon: 3-12 months

Opportunity score: 73/100
Expected value score: 74/100
Confidence score: 71/100
Timing score: 66/100
Risk score: 58/100
Liquidity score: 84/100

Why it triggered:
1. Current price is below the lower fair-value band.
2. Valuation is cheap versus peers and own history.
3. EPS estimates revised upward over 3 months.
4. Sector-relative momentum improved.
5. News sentiment improved after earnings.

Main risks:
1. Estimate dispersion is medium-high.
2. Earnings are in 9 days.
3. DCF target is sensitive to margin assumptions.

Invalidation:
1. Fair value falls below 90.
2. EPS revisions turn negative.
3. Price breaks below 72 on heavy volume.

Suggested category:
High-priority research review.
```

---

## 16. What the system should teach you over time

The system is not just for alerts. It should help you learn.

It should answer:

- Which signal families actually work for your universe?
- Which alerts led to good outcomes?
- Which alerts were false positives?
- Did valuation gaps close?
- Did timing signals improve results?
- Did sentiment add value or noise?
- Did high-risk names produce worse drawdowns?
- Which sectors need custom logic?
- Are analyst revisions more useful than social sentiment?
- Is the model over-alerting?
- Is the model missing obvious opportunities?

This means every alert needs outcome tracking.

Without outcome tracking, the system becomes a sophisticated opinion generator.

With outcome tracking, it becomes a learning machine.

---

## 17. Source principles behind this design

The design follows the combined lessons from the research:

1. Factor frameworks commonly include value, quality, momentum, volatility, size, yield, growth, liquidity, and sector context.
2. Stock ranking systems often combine quality, value, and momentum.
3. Analyst revisions and estimate surprises are useful timing and expectation-change signals.
4. News and social sentiment are useful but noisy; they should confirm or warn, not dominate.
5. Alternative data can nowcast fundamentals, but must be validated.
6. A trading system should optimize expected value and risk-adjusted returns, not raw prediction accuracy.
7. Drawdown, position sizing, liquidity, and survivability matter as much as entry signals.
8. Every signal must be validated with point-in-time data and tracked after alerts.

Source anchors:

- Morningstar investment factors: https://www.morningstar.com/investing-terms/investment-factor
- Morningstar Factor Profile: https://www.morningstar.com/products/factor-profile
- MSCI factor indexes: https://www.msci.com/indexes/factor-indexes/msci-factor-indexes
- MSCI factor models: https://www.msci.com/our-solutions/factor-investing/factor-models
- Stockopedia StockRanks: https://www.stockopedia.com/stockranks/
- S&P Global Alpha Signals: https://www.spglobal.com/market-intelligence/en/solutions/products/quantitative-equity-data-alpha-signals
- LSEG StarMine Analyst Revisions: https://www.lseg.com/en/data-analytics/financial-data/analytics/quantitative-analytics/starmine-analyst-revisions-models
- Qlib data/model docs: https://qlib.readthedocs.io/en/latest/component/data.html?highlight=alpha158
- Open Source Asset Pricing: https://www.openassetpricing.com/
- RiceQuant factor system: https://www.ricequant.com/doc/quant/factor-system
- JoinQuant factor library: https://www.joinquant.com/view/factorlib/list
- TurtleSignal backtesting guide: https://doc.turtlesignal.com/zh/practice/backtesting/
- QuantConnect optimization objectives: https://www.quantconnect.com/docs/v2/cloud-platform/optimization/objectives
- QuantStart backtesting guide: https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-I/
- Van Tharp position sizing/risk management: https://vantharpinstitute.com/van-tharp-teaches-position-sizing-strategies-and-risk-management/

---

## 18. Final definition

The target trading system is:

```text
A risk-adjusted target-opportunity monitor that estimates fair-value ranges,
calculates expected value, confirms timing, controls risk, and produces
explainable alerts when current price diverges meaningfully from fair value.
```

The core input groups are:

```text
market data
fundamentals
valuation data
analyst estimates/revisions
momentum
sentiment/news/social
catalysts/events
macro/sector/peer context
volatility/risk/liquidity
positioning/flows
options-implied data
alternative data
governance/accounting/legal risk
portfolio/user constraints
```

The core output groups are:

```text
target price range
valuation gap
expected value
confidence score
timing score
risk score
liquidity score
opportunity score
alert type
alert priority
reason codes
risk codes
invalidation conditions
position-review category
outcome tracking
```

The most important rule:

```text
No alert should fire just because target price is above current price.
An alert should fire only when target gap, expected value, confidence,
timing, liquidity, and risk all pass the system's standards.
```

