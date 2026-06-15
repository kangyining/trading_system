# Online postings summary: signal components for a target-price alert system

Created on 2026-06-05.

User goal:

> Build a system that gives a target/fair price and alerts when current price diverges too much from that target.

I checked public methodology pages, articles, docs, academic papers, and discussion posts about equity signals, factor models, stock ranking systems, target-price models, analyst revisions, sentiment, and alternative data.

## The big lesson

Most good public systems do **not** rely on one signal. They combine:

1. A **valuation/fair-value anchor**,
2. **Quality/fundamentals**,
3. **Growth and revisions**,
4. **Momentum and trend confirmation**,
5. **Sentiment and news**,
6. **Risk, volatility, and liquidity filters**,
7. **Catalysts, positioning, and flows**,
8. **Model confidence and validation**.

For your target-price monitor, the core equation is:

```text
divergence = (target_price - current_price) / current_price
```

But the alert should not trigger on divergence alone. It should trigger on:

```text
meaningful divergence
+ confidence
+ fresh data
+ acceptable liquidity
+ explainable reason codes
+ no obvious value-trap / stale-price warning
```

## What public factor models agree on

### Morningstar

Morningstar's public factor profile identifies seven broad factors:

- Style / value-growth
- Yield
- Momentum
- Quality
- Volatility
- Liquidity
- Size

Teaching point:

Your list has fundamentals, momentum, and sentiment, but Morningstar's framework reminds us that **volatility, liquidity, size, yield, and value-growth style** should also be tracked.

Sources:

- https://www.morningstar.com/investing-terms/investment-factor
- https://www.morningstar.com/products/factor-profile
- https://www.morningstar.com/content/dam/marketing/shared/Company/Products/Direct_Cloud/RiskModel_Global_Methodology.pdf

### MSCI

MSCI groups common equity factors into:

- Value
- Size
- Momentum
- Volatility
- Quality
- Yield
- Growth
- Liquidity

Teaching point:

This is close to Morningstar, and it gives a clean backbone for your signal taxonomy. If a proposed signal does not fit into one of these or into a newer alternative-data bucket, it needs extra justification.

Sources:

- https://www.msci.com/research-and-insights/blog-post/creating-a-common-language-for-factor-investing
- https://www.msci.com/indexes/factor-indexes/msci-factor-indexes

### Stockopedia

Stockopedia's public StockRanks framework emphasizes:

- Quality
- Value
- Momentum

Their momentum discussion also includes analyst sentiment and estimate direction.

Teaching point:

Quality, value, and momentum are the simplest teachable trio. But for your system, they are not enough because you also need target-price construction, uncertainty bands, and alert logic.

Sources:

- https://www.stockopedia.com/stockranks/
- https://www.stockopedia.com/academy/articles/what-are-the-stockranks
- https://www.stockopedia.com/learn/stockranks-ratings/the-value-rank-463093//

### Factor-Based

Factor-Based's methodology uses:

- Value = valuation
- Quality = quality + volatility
- Momentum = technical + growth + revisions

Teaching point:

This is especially relevant because it separates **growth and analyst revisions** from pure price momentum. That is useful for your target-price system because revisions often update the target before reported fundamentals catch up.

Source:

- https://factorbased.com/rankings/methodology

### S&P Global Alpha Signals

S&P describes a broad factor library built from:

- Fundamental data
- Technical data
- Industry-specific data
- Proprietary data
- Alternative data

Teaching point:

Once the basic model works, sector-specific and alternative-data signals become the edge layer.

Source:

- https://www.spglobal.com/market-intelligence/en/solutions/products/quantitative-equity-data-alpha-signals

## Components and how to think about them

### 1. Valuation / fair-value anchor

This is the most important component for your goal.

Valuation answers:

> What should the stock be worth?

Common methods:

- DCF
- Relative valuation
- Historical multiples
- Peer multiples
- Reverse DCF
- Residual income
- Dividend discount model
- NAV / sum-of-parts
- Analyst consensus target

Online postings about valuation tools converge on one point: use a **blend** or **range**, not one magic target. DCF is sensitive to assumptions; multiples can inherit market mispricing; analyst targets can lag price. Blending reduces single-model bias.

Practical design:

```text
target_price = weighted_blend(
  DCF_target,
  relative_valuation_target,
  historical_multiple_target,
  analyst_target,
  reverse_DCF_sanity_check
)
```

Sources:

- https://www.alphaspread.com/
- https://www.fairpriceindex.com/
- https://www.footnotesanalyst.com/target-ev-multiples/
- https://www.morningstar.com/content/dam/marketing/shared/research/methodology/705988Morningstar_Equity_Research_Methodology.pdf
- https://en.wikipedia.org/wiki/Stock_valuation

### 2. Quality / fundamentals

Quality answers:

> Is this business good enough for the target to be trusted?

Subsignals:

- ROIC / ROE / ROA
- Gross margin and operating margin
- Cash conversion
- Free cash flow quality
- Accruals
- Earnings stability
- Balance sheet strength
- Leverage
- Interest coverage
- Bankruptcy risk

Teaching point:

Cheap plus low quality is often a **value trap**. Cheap plus high quality is more interesting.

```text
if valuation_gap_positive and quality_score_low:
  label = "possible value trap"
```

Sources:

- https://www.stockopedia.com/stockranks/
- https://factorbased.com/rankings/methodology
- https://blankcapitalresearch.com/learn/how-we-rank-stocks

### 3. Growth expectations

Growth answers:

> Are future earnings and cash flows improving or deteriorating?

Subsignals:

- Revenue growth
- EPS growth
- FCF growth
- Margin expansion
- Backlog/bookings
- Unit economics
- Product cycle
- TAM/runway

Teaching point:

Growth is not the same as momentum. Momentum is market behavior; growth is business trajectory.

For target price:

```text
justified_multiple = f(growth, quality, rates, risk)
target = forward_metric * justified_multiple
```

Sources:

- https://factorbased.com/rankings/methodology
- https://www.stockopedia.com/stockranks/

### 4. Analyst revisions and earnings surprise

This is one of the most important missing buckets from the original list.

Subsignals:

- EPS revisions
- Revenue revisions
- EBITDA / FCF revisions
- Buy/hold/sell recommendation changes
- Target-price revisions
- Estimate dispersion
- Earnings surprise
- Post-earnings announcement drift

The StarMine Analyst Revisions Model is a good public example: it ranks stocks based on changes in analyst estimates for earnings, revenue, EBITDA, and analyst recommendations.

Teaching point:

Revisions tell you whether the market's model of the company is moving up or down. For a target-price system, revisions should update both the target and confidence.

```text
revision_score = EPS_revision_score
               + revenue_revision_score
               + target_price_revision_score
               - estimate_dispersion_penalty
```

Sources:

- https://www.lseg.com/en/data-analytics/financial-data/analytics/quantitative-analytics/starmine-analyst-revisions-models
- https://www.sciencedirect.com/science/article/pii/S2214635020303750
- https://pomegra.io/learn/library/track-b-stock-market-core/earnings/chapter-09-revisions-and-surprise/post-earnings-drift-pead
- https://bigquant.com/square/paper/2536e550-1fc4-41ce-9bfa-4a3fbd2d5aa2

### 5. Momentum

Momentum answers:

> Is the market confirming or rejecting the thesis right now?

Subsignals:

- 1M, 3M, 6M, 12M price momentum
- 12-minus-1 momentum
- Relative strength vs market
- Relative strength vs sector
- Moving average trend
- Breakout / 52-week high proximity
- Short-term reversal
- Volume-confirmed momentum
- Residual momentum after sector/market neutralization

Teaching point:

Momentum should not set the target price by itself. It should decide whether a target-price gap is early, confirmed, or contradicted.

```text
if target_gap_positive and momentum_positive:
  signal_type = "undervalued with confirmation"

if target_gap_positive and momentum_negative:
  signal_type = "contrarian / falling knife check needed"
```

Sources:

- https://www.stockopedia.com/stockranks/
- https://factorbased.com/rankings/methodology
- https://www.msci.com/indexes/factor-indexes/msci-factor-indexes

### 6. Sentiment

Sentiment answers:

> What does the crowd/news/analyst ecosystem currently believe?

Break sentiment into channels:

- Social sentiment: Reddit, X, StockTwits, etc.
- Social attention: mention volume and acceleration.
- News sentiment.
- Analyst sentiment.
- Earnings-call sentiment.
- Filing sentiment.
- Search interest.
- Employee/customer sentiment.

Teaching point:

Social media is only one sentiment source and is often noisy. News/analyst/earnings-call sentiment may be cleaner for stock-specific target-price updates.

Sources:

- https://www.msci.com/research-and-insights/paper/introducing-news-sentiment-a-systematic-equity-strategy-factor
- https://www.lseg.com/en/data-analytics/resources/white-paper/the-value-of-alternative-data-and-media-sentiment
- https://arxiv.org/abs/2301.09279
- https://arxiv.org/abs/2203.12460

### 7. Risk, volatility, and uncertainty band

Risk answers:

> How far can price normally move before the divergence is actually meaningful?

Subsignals:

- Realized volatility
- Implied volatility
- Beta
- Idiosyncratic volatility
- Drawdown
- Options-implied move
- Target-price dispersion
- Estimate dispersion
- Model historical error

Teaching point:

A 15% gap is huge for a sleepy utility and normal for a biotech. Alerts need volatility-adjusted thresholds.

```text
required_gap = max(
  minimum_gap,
  volatility_buffer,
  model_error_buffer,
  target_dispersion_buffer,
  event_risk_buffer
)
```

Sources:

- https://www.morningstar.com/content/dam/marketing/shared/Company/Products/Direct_Cloud/RiskModel_Global_Methodology.pdf
- https://www.sciencedirect.com/science/article/pii/S106294082100022X

### 8. Liquidity and data reliability

Liquidity answers:

> Can I trust the displayed price?

Subsignals:

- Dollar volume
- Bid/ask spread
- Share turnover
- Float
- Stale price flag
- Halt flag
- Corporate action adjustment

Teaching point:

Even if you are not executing trades, liquidity matters because bad prices create false divergence alerts.

Sources:

- https://www.morningstar.com/content/dam/marketing/shared/Company/Products/Direct_Cloud/RiskModel_Global_Methodology.pdf
- https://www.factorstoday.com/about

### 9. Positioning and flows

Positioning answers:

> Who is already crowded into or against the stock?

Subsignals:

- Short interest
- Days to cover
- Borrow cost
- Options implied volatility skew
- Put/call volume
- Options open interest
- Insider buying/selling
- Institutional ownership changes
- ETF/index flows
- Congressional trades, if monitored

Teaching point:

Positioning does not create fair value, but it can explain why price diverges and whether the gap can snap back violently.

Sources:

- https://www.sciencedirect.com/science/article/pii/S0378426614003616
- https://www.sciencedirect.com/science/article/pii/S1386418123000393
- https://journals.sagepub.com/doi/10.1177/0148558X0101600206

### 10. Catalysts and event timing

Catalysts answer:

> What could close the gap?

Subsignals:

- Earnings date
- Guidance changes
- Product launches
- Regulatory decisions
- Litigation
- M&A
- Buybacks/dividends
- Index inclusion
- Investor days
- Lockup expiry

Teaching point:

A stock can be mispriced for months if there is no catalyst. Your alert should say whether divergence is merely interesting or timely.

```text
if large_gap and catalyst_within_30d:
  alert_priority += 1
```

Sources:

- https://www.bamboosignal.com/methodology
- https://pomegra.io/learn/library/track-b-stock-market-core/earnings/chapter-09-revisions-and-surprise/post-earnings-drift-pead

### 11. Macro, sector, and regime

Regime answers:

> Is the environment friendly or hostile to this signal?

Subsignals:

- Rates
- Credit spreads
- Inflation
- FX
- Commodity prices
- VIX / volatility regime
- Market trend
- Sector momentum
- Sector valuation
- Factor regime
- Yield curve

Teaching point:

Do not interpret a target-price gap in isolation. A cheap bank, cheap oil stock, cheap software company, and cheap utility all mean different things depending on rates, credit, commodities, and sector regime.

Sources:

- https://arxiv.org/abs/2601.19504
- https://bigquant.com/square/paper/60e76d93-ae76-4466-bbca-2d8c924fa6ce

### 12. Alternative data

Alternative data answers:

> Is real-world behavior changing before fundamentals and consensus catch up?

Subsignals:

- Web traffic
- App downloads
- Credit/debit card data
- Geolocation / foot traffic
- Satellite imagery
- Job postings
- Patent data
- Shipping/imports
- Product pricing
- Reviews
- Search trends
- Wikipedia views

Teaching point:

Alternative data is not magic. It is useful when it maps cleanly to an economic question, such as "are customers visiting stores more often?" or "is app usage accelerating?"

Sources:

- https://www.similarweb.com/blog/investor/asset-research/what-is-alternative-data/
- https://www.lseg.com/en/data-analytics/financial-data/alternative-data
- https://en.wikipedia.org/wiki/Alternative_data_%28finance%29

## What discussion posts add

Public discussion posts are noisier than methodology pages, but they add practical warnings:

1. **Analyst price targets often lag price.** Revisions and underlying estimate changes may be more useful than the target level itself.
2. **DCF outputs are fragile.** Small changes in growth, discount rate, or terminal assumptions can change target price dramatically.
3. **Alternative data needs validation.** Vendor backtests are not enough; you need point-in-time history and live trial behavior.
4. **Signals work best in combination.** A single sentiment score or social-media spike is weak. Convergence across independent signals is stronger.
5. **Rankings are research aids, not automatic buys.** High score means "worth investigating," not "buy now."

Useful discussion sources:

- https://www.reddit.com/r/stocks/comments/14bbgeg/analysts_are_a_silly_bunch_they_revise_their_because_they_dont_want_to_get_laughed_at_leading_people_to_lose_money/
- https://www.reddit.com/r/ValueInvesting/comments/1qok0w1/testing_a_dcf_valuation_tool_where_do_these_usually_mislead_investors/
- https://www.reddit.com/r/quant/comments/1oqyofk/working_with_backtests_from_alternative/
- https://www.reddit.com/r/quant/comments/198icn8/alternative_data_for_quant/

## How to build your mental model

Think of each stock as having three prices:

| Price | Meaning |
|---|---|
| Market price | What the market says now. |
| Model target price | What your valuation/revision model says it should be worth. |
| Confidence-adjusted fair-value band | The realistic range after uncertainty, volatility, dispersion, and model error. |

You only care when:

```text
market_price is outside the confidence-adjusted fair-value band
```

Then ask:

1. Is the target based on valuation or just vibes?
2. Is business quality good enough?
3. Are revisions moving with or against the target?
4. Is momentum confirming or fighting the signal?
5. Is sentiment/news improving or deteriorating?
6. Is the gap large relative to volatility?
7. Is the price liquid and fresh?
8. Is there a catalyst?
9. Is positioning crowded?
10. Has this model worked out-of-sample?

## Version 1 system blueprint

Start with these modules:

```text
1. Universe and data freshness
2. Valuation target engine
3. Quality/fundamentals score
4. Growth and analyst revisions score
5. Momentum score
6. Sentiment/news score
7. Risk/volatility/liquidity filter
8. Catalyst and positioning flags
9. Divergence alert engine
10. Explanation and audit log
```

The alert should look like:

```text
Ticker: XYZ
Current price: 84.20
Target range: 101-118
Base target: 109
Upside gap: +29.5%
Required gap: 17.0%
Signal: Bullish divergence
Confidence: Medium-high
Main reasons:
  1. Relative valuation 22% below peers
  2. EPS estimates revised up 8% over 90 days
  3. Price momentum recovering above sector
Main risks:
  1. Analyst target dispersion high
  2. Earnings in 9 days
  3. Liquidity below preferred threshold
```

## Short answer

The online material says your original list should become:

```text
valuation
+ fundamentals / quality
+ growth
+ analyst revisions
+ momentum
+ social/news/analyst sentiment
+ volatility and risk
+ liquidity
+ macro/sector regime
+ catalysts
+ positioning and flows
+ alternative data
+ validation/model health
```

The target-price part should be taught as:

```text
target price is not a signal by itself
target price + uncertainty band + current price divergence + confirmation = signal
```

