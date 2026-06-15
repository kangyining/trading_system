# Granular signal taxonomy and systematic blueprint

Created: 2026-06-05

Purpose: design a signal system that estimates a target/fair-value range, compares it with market price, and alerts only when the divergence is large enough to matter.

This file expands the earlier component list into a more granular, wider, systematic framework based on online sources from factor providers, quant platforms, academic papers, and practitioner discussions.

Important: this is research and system design, not investment advice.

---

## 1. The high-level architecture

Your end goal is not just:

```text
predict next price
```

It is closer to:

```text
estimate fair value range
+ estimate expected return / ranking score
+ estimate uncertainty
+ check catalyst timing
+ alert when market price diverges too much
```

The useful system split is:

1. Target-price engine: "What should this asset be worth?"
2. Alpha / return-prediction engine: "Is the price likely to move toward that target?"
3. Confidence / uncertainty engine: "How wide should the fair-value band be?"
4. Risk / liquidity filter: "Can this signal be trusted and acted on?"
5. Catalyst / timing layer: "Why might the gap close now?"
6. Alert engine: "Is the divergence big enough after all filters?"
7. Explanation layer: "Why did the alert fire?"
8. Validation layer: "Has this signal historically worked without leakage?"

The target price should usually be a range, not a single number.

```text
current_price = live/last price
base_target = blended fair value estimate
target_low = base_target * (1 - uncertainty_band)
target_high = base_target * (1 + uncertainty_band)
upside_to_base = base_target / current_price - 1
upside_to_low = target_low / current_price - 1
```

Alert idea:

```text
if current_price < target_low
and upside_to_base > required_gap
and confidence_score >= minimum_confidence
and liquidity_score >= minimum_liquidity
and data_freshness_ok
then bullish_divergence_alert
```

---

## 2. What the online sources agree on

The broad consensus from Morningstar, MSCI/Barra, BlackRock, Stockopedia, S&P Global, RiceQuant, JoinQuant, FactorHub, Qlib, and academic factor datasets is that equity signals cluster into repeatable families:

- Value / valuation
- Quality / profitability / financial strength
- Growth
- Earnings revisions / analyst expectations
- Momentum / reversal / price-volume
- Volatility / beta / risk
- Liquidity / tradability
- Size
- Yield / capital return
- Sentiment / news / social media
- Industry / sector / peer context
- Macro / regime
- Positioning / ownership / flows
- Options-implied information
- Alternative data
- Governance / legal / accounting risk
- Event / catalyst timing
- Model health / validation

Your original list had:

```text
fundamentals, momentum, sentiment
```

That is a good start, but too compressed. In a production-style system, "fundamentals" should be split into valuation, quality, growth, balance sheet, cash flow, capital allocation, analyst revisions, and accounting risk. "Sentiment" should split into news sentiment, social sentiment, analyst sentiment, attention, topic novelty, and event sentiment.

---

## 3. A more systematic signal hierarchy

Use this hierarchy as the folder structure or database taxonomy for the signal system.

```text
00_data_quality_and_universe
01_valuation_fair_value
02_quality_profitability
03_growth_expectations
04_balance_sheet_and_financial_strength
05_cash_flow_and_capital_allocation
06_earnings_revisions_and_surprises
07_price_momentum_and_reversal
08_volume_liquidity_and_market_microstructure
09_volatility_beta_and_uncertainty
10_news_social_and_text_sentiment
11_catalysts_and_events
12_sector_peer_and_supply_chain_context
13_macro_regime_and_factor_timing
14_positioning_ownership_and_flows
15_options_implied_signals
16_alternative_data
17_governance_legal_and_accounting_risk
18_asset_specific_modules
19_model_validation_and_monitoring
20_alert_logic_and_explanation
```

---

## 4. The signal schema

Every signal should have the same metadata. This keeps the system clean.

```yaml
signal_id: valuation.forward_pe_sector_z
family: valuation
raw_fields:
  - forward_eps
  - current_price
  - sector_peer_forward_pe
transform:
  - compute forward_pe
  - winsorize within sector
  - convert to sector-relative z-score
expected_direction: lower is cheaper / more bullish, unless fundamentals are deteriorating
horizon: 3-12 months
data_lag: estimate date, fiscal period, vendor timestamp
neutralization:
  - sector
  - market_cap_bucket
score_method: percentile_rank
target_price_effect: direct input to relative valuation target
confidence_effect: medium
alert_effect: bullish if cheap and quality/growth are not broken
validation:
  - RankIC
  - quantile return spread
  - turnover
  - hit rate after transaction cost
failure_modes:
  - value trap
  - stale estimates
  - wrong peer group
  - cyclical earnings peak/trough
```

This schema matters because two signals with the same score can have different jobs. For example:

- DCF fair value directly changes target price.
- Momentum may not change fair value, but changes the chance that price starts moving.
- Volatility may not say bullish or bearish, but widens the band and raises the required alert threshold.
- Liquidity may not change expected return, but decides whether to ignore the signal.

---

## 5. Granular signal catalog

### 5.1 Data quality and universe

Question: "Is this instrument even eligible for signals?"

Raw inputs:

- Price
- Adjusted close
- Volume
- Market cap
- Free float
- Listing date
- Exchange
- Currency
- Sector / industry
- Corporate actions
- Delisting status
- Suspensions / halts
- ADR/native listing mapping
- Split and dividend adjustments
- Reporting calendar
- Data vendor timestamps

Useful features:

- Minimum market cap
- Minimum dollar volume
- Minimum price
- Trading days since IPO
- Missing-value rate
- Stale quote flag
- Split-adjustment sanity check
- Corporate action flag
- Reporting-date freshness
- Point-in-time availability flag

System role:

- Hard filter before any signal.
- Prevents false alerts from stale data, illiquid names, broken corporate-action adjustments, or post-delisting bias.

Failure modes:

- Survivorship bias
- Look-ahead bias
- Restated fundamentals used too early
- Split-adjusted price mismatch
- Symbol changes
- ADR/native double counting

---

### 5.2 Valuation / fair-value anchor

Question: "What should this company be worth?"

This is the core target-price engine.

Raw inputs:

- Current price
- Shares outstanding / diluted shares
- Enterprise value
- Revenue
- Gross profit
- EBITDA
- EBIT
- Net income
- EPS
- Free cash flow
- Book value
- Tangible book value
- Net debt
- Dividends
- Buybacks
- Analyst forward estimates
- Sector peer multiples
- Historical own multiples
- Discount rate assumptions
- Long-term growth assumptions

Granular signals:

- Trailing P/E
- Forward P/E
- PEG
- EV/Revenue
- EV/EBITDA
- EV/EBIT
- Price/book
- Price/tangible book
- Price/free cash flow
- Dividend yield
- Shareholder yield
- FCF yield
- Earnings yield
- Sales yield
- Gross profit / enterprise value
- EV/EBITDA versus sector
- P/E versus own 5-year history
- FCF yield versus bond yield
- ROIC minus WACC
- Reverse DCF implied revenue growth
- Reverse DCF implied margin
- Scenario DCF fair value
- Sum-of-the-parts fair value
- Liquidation / tangible book support
- Net cash as percent of market cap
- Net debt / enterprise value

Target-price methods:

- Relative multiple target:

```text
target_price = selected_peer_multiple * forward_metric / diluted_shares
```

- Historical multiple target:

```text
target_price = normalized_own_multiple * normalized_forward_metric
```

- DCF target:

```text
enterprise_value = discounted_forecast_fcf + discounted_terminal_value
equity_value = enterprise_value - net_debt
target_price = equity_value / diluted_shares
```

- Reverse DCF:

```text
implied_growth = growth rate required to justify current price
signal = bullish if implied assumptions look too pessimistic
```

System role:

- Directly creates the target price.
- Should produce base target, low target, high target, and assumptions.

Failure modes:

- Cheap stocks can stay cheap.
- Cyclical earnings can make P/E misleading.
- DCF terminal value dominates the output.
- Peer group choice can drive the answer.
- Analyst estimates may lag reality.
- High-growth companies can look expensive for years.

Source anchors:

- Morningstar fair value and moat methodology: https://www.morningstar.com/business/insights/blog/markets/equity-economic-moat-ratings
- Morningstar fair value glossary: https://admainnew.morningstar.com/webhelp/glossary_definitions/stocks/stocksglossary_Morningstar_Fair_Value.html
- Stock valuation overview: https://en.wikipedia.org/wiki/Stock_valuation
- AlphaSpread valuation examples: https://www.alphaspread.com/
- Footnotes Analyst on target EV multiples: https://www.footnotesanalyst.com/target-ev-multiples/

---

### 5.3 Quality / profitability

Question: "Is this a good business, or just statistically cheap?"

Raw inputs:

- Gross profit
- Operating income
- Net income
- Cash flow from operations
- Free cash flow
- Assets
- Equity
- Invested capital
- Debt
- Interest expense
- Working capital
- Accruals
- Margins

Granular signals:

- Gross margin
- Operating margin
- Net margin
- Margin stability
- Gross profit / assets
- ROA
- ROE
- ROIC
- ROIC stability
- ROIC minus WACC
- Cash conversion
- Free cash flow margin
- CFO / net income
- Accruals ratio
- Earnings variability
- Revenue stability
- Operating leverage
- Asset turnover
- Inventory turnover
- Receivables days
- Payables days
- Interest coverage
- Debt / EBITDA
- Net debt / EBITDA
- Altman Z-score
- Piotroski F-score
- Beneish M-score
- Ohlson O-score
- Auditor change flag
- Restatement flag

System role:

- Increases/decreases target confidence.
- Helps avoid value traps.
- Can justify a premium multiple for high-quality companies.

Failure modes:

- Quality metrics lag.
- Banks, insurers, REITs, and early-stage growth companies need custom metrics.
- Margin strength may be cyclical or temporary.

Source anchors:

- AQR Quality Minus Junk: https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk
- Stockopedia StockRanks: https://www.stockopedia.com/stockranks/
- Factor-Based ranking methodology: https://factorbased.com/rankings/methodology

---

### 5.4 Growth expectations

Question: "Is the business improving fast enough to justify the valuation?"

Raw inputs:

- Revenue
- EPS
- EBITDA
- EBIT
- FCF
- Bookings
- Backlog
- Customers
- Units
- Same-store sales
- ARPU
- ARR/MRR for SaaS
- Net retention
- Analyst forward estimates

Granular signals:

- Revenue growth YoY
- Revenue growth QoQ
- 3-year revenue CAGR
- EPS growth
- EBITDA growth
- FCF growth
- Gross profit growth
- Bookings growth
- Backlog growth
- Guidance growth
- Analyst expected growth
- Growth acceleration
- Growth deceleration
- Rule of 40 for SaaS
- R&D intensity
- Sales and marketing efficiency
- Capex growth
- Unit volume growth
- Price/mix growth
- Customer count growth
- Net revenue retention
- Churn rate

System role:

- Drives DCF assumptions and forward multiples.
- Changes whether a high multiple is justified.
- Alerts when current price implies too little or too much future growth.

Failure modes:

- Growth without unit economics can destroy value.
- Growth deceleration can matter more than absolute growth.
- One-time reopening/cycle effects can fool the model.

Source anchors:

- RiceQuant factor categories: https://www.ricequant.com/doc/quant/factor-system
- FactorHub category taxonomy: https://factorhub.cn/
- JoinQuant factor library: https://www.joinquant.com/view/factorlib/list

---

### 5.5 Balance sheet and financial strength

Question: "Can this company survive stress?"

Raw inputs:

- Cash
- Short-term investments
- Debt
- Maturity schedule
- Interest expense
- EBITDA
- CFO
- FCF
- Current assets
- Current liabilities
- Covenants
- Credit rating
- Credit spread

Granular signals:

- Net cash / market cap
- Net debt / EBITDA
- Debt / equity
- Interest coverage
- Current ratio
- Quick ratio
- Debt maturity wall
- Free cash flow after interest
- Credit rating change
- CDS spread change if available
- Bond yield spread
- Covenant risk flag
- Refinancing risk flag

System role:

- Widens fair-value band if leverage is high.
- Lowers confidence for distressed companies.
- Can create upside if market overprices bankruptcy risk.

Failure modes:

- Book debt does not reveal all obligations.
- Off-balance-sheet liabilities matter.
- Financial companies need different leverage metrics.

---

### 5.6 Cash flow and capital allocation

Question: "Does management turn earnings into owner value?"

Raw inputs:

- CFO
- Capex
- FCF
- Dividends
- Buybacks
- Share count
- SBC
- Acquisitions
- Debt issuance/repayment

Granular signals:

- FCF yield
- CFO / net income
- Capex / sales
- Maintenance capex estimate
- Buyback yield
- Dividend yield
- Net payout yield
- Share count reduction
- Share-based compensation / revenue
- Acquisition intensity
- Acquisition impairment history
- Return on incremental invested capital
- Dividend coverage
- Buyback timing quality

System role:

- Helps decide whether the target price should compound.
- Detects companies where EPS growth is financial engineering.

Failure modes:

- Buybacks can destroy value if done at expensive prices.
- FCF can be temporarily boosted by working-capital timing.

---

### 5.7 Analyst revisions and earnings surprise

Question: "Are professional expectations moving up or down?"

Raw inputs:

- Consensus EPS
- Consensus revenue
- Consensus EBITDA
- Consensus FCF
- Analyst target prices
- Buy/hold/sell ratings
- Estimate dates
- Number of analysts
- Dispersion of estimates
- Recent revisions
- Reported earnings
- Guidance

Granular signals:

- 1-month EPS revision
- 3-month EPS revision
- Revenue revision
- EBITDA revision
- FCF revision
- Number of up revisions
- Number of down revisions
- Revision breadth
- Recommendation upgrade/downgrade
- Target price revision
- Consensus target upside
- Target price dispersion
- Estimate dispersion
- Smart estimate / consensus gap
- Predicted surprise
- Standardized unexpected earnings (SUE)
- Earnings surprise
- Revenue surprise
- Guidance surprise
- Post-earnings announcement drift signal

System role:

- Changes expected drift toward target.
- Can move target price when forward fundamentals change.
- Good timing layer around earnings.

Failure modes:

- Analyst targets often lag price moves.
- High target-price dispersion means low confidence.
- Upward revisions after a large rally may be late.

Source anchors:

- LSEG StarMine Analyst Revisions Models: https://www.lseg.com/en/data-analytics/financial-data/analytics/quantitative-analytics/starmine-analyst-revisions-models
- LSEG SmartEstimates: https://www.lseg.com/en/data-analytics/financial-data/analytics/quantitative-analytics/starmine-smartestimates
- Analyst target price dispersion paper: https://www.sciencedirect.com/science/article/pii/S106294082100022X
- Analyst target price accuracy research: https://www.tandfonline.com/doi/abs/10.1080/15427560.2024.2368151
- PEAD review: https://www.sciencedirect.com/science/article/pii/S2214635020303750

---

### 5.8 Price momentum and reversal

Question: "Is the market already moving in the same direction?"

Raw inputs:

- Open/high/low/close
- Adjusted close
- Volume
- Market index return
- Sector return
- Peer return

Granular signals:

- 1-month return
- 3-month return
- 6-month return
- 12-month return excluding last month
- Short-term reversal
- 52-week high distance
- Relative strength versus market
- Relative strength versus sector
- Industry momentum
- Residual momentum after beta/sector adjustment
- Volatility-adjusted momentum
- Moving-average slope
- Moving-average crossover
- Breakout from range
- Drawdown from high
- New high / new low
- RSI
- MACD
- Bollinger band position
- Trend consistency
- Gap up/down
- Post-earnings gap continuation

System role:

- Confirms whether price may converge toward target.
- Can stop value signals from firing too early.
- Helps rank watchlist names.

Failure modes:

- Momentum crashes.
- Short-term reversal can conflict with medium-term momentum.
- Sector momentum may dominate stock-specific momentum.

Source anchors:

- Jegadeesh and Titman momentum paper: https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1993.tb04702.x
- Industry momentum paper: https://onlinelibrary.wiley.com/doi/pdf/10.1111/0022-1082.00146
- MSCI factor indexes: https://www.msci.com/indexes/factor-indexes/msci-factor-indexes
- Qlib Alpha158 handler: https://qlib.readthedocs.io/en/latest/component/data.html?highlight=alpha158
- WorldQuant 101 Formulaic Alphas: https://arxiv.org/abs/1601.00991

---

### 5.9 Volume, liquidity, and market microstructure

Question: "Is the price reliable and tradable?"

Raw inputs:

- Volume
- Dollar volume
- Bid/ask spread
- High/low
- Turnover
- Shares outstanding
- Free float
- Intraday bars if available

Granular signals:

- Average daily dollar volume
- Turnover ratio
- Bid/ask spread
- Amihud illiquidity
- High-low spread estimate
- Volume spike
- Volume trend
- Volume-price divergence
- On-balance volume
- Accumulation/distribution
- VWAP deviation
- Gap with volume confirmation
- Float turnover
- Days to cover

System role:

- Filters untradable signals.
- Widens required alert gap for illiquid names.
- Helps distinguish meaningful breakouts from noise.

Failure modes:

- Low liquidity can create false price gaps.
- Volume spikes around events can mean distribution, not accumulation.

Source anchors:

- Morningstar risk model/factor profile: https://www.morningstar.com/products/factor-profile
- RiceQuant factor system: https://www.ricequant.com/doc/quant/factor-system
- JoinQuant factor library: https://www.joinquant.com/view/factorlib/list

---

### 5.10 Volatility, beta, and uncertainty band

Question: "How uncertain is the target, and how large must the divergence be?"

Raw inputs:

- Historical returns
- Market index returns
- Sector returns
- Options implied volatility
- Earnings calendar
- Analyst dispersion
- Liquidity

Granular signals:

- Realized volatility
- Downside volatility
- Beta to market
- Beta to sector
- Idiosyncratic volatility
- Residual volatility
- Max drawdown
- Drawdown duration
- Value at risk
- Expected shortfall
- Volatility regime
- Correlation to market
- Correlation to sector
- Analyst estimate dispersion
- Target price dispersion
- Event risk window
- Illiquidity risk

System role:

- Sets band width.
- Sets minimum required gap.
- Controls false positives.

Possible formula:

```text
uncertainty_band =
  base_band
  + volatility_component
  + estimate_dispersion_component
  + liquidity_penalty
  + event_risk_penalty
```

Failure modes:

- Backward-looking volatility misses sudden regime change.
- Low volatility can hide fundamental risk.
- High volatility may create apparent upside that is just noise.

Source anchors:

- Morningstar investment factor definitions: https://www.morningstar.com/investing-terms/investment-factor
- MSCI Barra equity factor models: https://www.msci.com/our-solutions/factor-investing/factor-models
- Betting Against Beta: https://www.nber.org/papers/w16601

---

### 5.11 News, social, and text sentiment

Question: "Is the narrative changing?"

Raw inputs:

- News headlines
- Full articles
- Press releases
- SEC filings
- Earnings call transcripts
- Analyst notes if licensed
- Social posts
- Reddit / X / StockTwits mentions
- Search trends
- Source credibility
- Timestamp
- Ticker/entity mapping

Granular signals:

- News sentiment
- News volume
- News novelty
- News relevance
- Event type classification
- Headline sentiment
- Article sentiment
- Earnings call tone
- Management tone change
- Q&A negativity
- Filing risk language change
- Social bullish/bearish score
- Social mention volume
- Social velocity
- Social attention spike
- Meme-stock attention flag
- Influencer/source-weighted sentiment
- Bot/spam-adjusted sentiment
- Sentiment disagreement
- Topic sentiment: AI, regulation, layoffs, product, litigation, demand, pricing

System role:

- Timing and confirmation layer.
- Can detect inflection before financial statements update.
- Can warn when valuation gap is caused by real negative news.

Failure modes:

- Most social sentiment is noisy.
- Attention is not always bullish.
- Generic positive headlines may already be priced in.
- Bot activity and coordinated promotion can pollute signals.

Source anchors:

- MSCI News Sentiment factor: https://www.msci.com/research-and-insights/paper/introducing-news-sentiment-a-systematic-equity-strategy-factor
- LSEG media sentiment white paper: https://www.lseg.com/en/data-analytics/resources/white-paper/the-value-of-alternative-data-and-media-sentiment
- RavenPack factor investing with sentiment: https://www.ravenpack.com/research/equity-factor-investing-enhanced-with-news-earnings-call-transcripts/
- StockTwits sentiment and returns: https://link.springer.com/article/10.1007/s42521-023-00102-z
- Social signal paper: https://www.sciencedirect.com/science/article/pii/S0304405X2400093X
- FinBERT sentiment example: https://arxiv.org/abs/2306.02136

---

### 5.12 Catalysts and events

Question: "What could close the price/target gap?"

Raw inputs:

- Earnings dates
- Product launch dates
- FDA/PDUFA dates
- Court dates
- Regulatory deadlines
- Investor day
- Conference appearances
- M&A rumors/announcements
- Dividend/buyback announcements
- Index rebalance dates
- Lockup expirations
- Debt maturity dates
- Macro release calendar

Granular signals:

- Days to earnings
- Earnings surprise history
- Guidance revision history
- Product launch proximity
- Regulatory approval probability
- Litigation event risk
- M&A probability / strategic fit
- Buyback authorization
- Dividend increase/decrease
- Activist involvement
- Spin-off / split-up catalyst
- Index inclusion/deletion
- Lockup expiration pressure
- Debt refinancing event

System role:

- Turns valuation gap into an actionable alert.
- Can raise or lower signal urgency.

Failure modes:

- Events can resolve against the thesis.
- Known catalysts may be crowded.
- Binary events need probability-weighted valuation.

---

### 5.13 Sector, peer, and supply-chain context

Question: "Is this stock cheap/strong relative to the right comparison group?"

Raw inputs:

- Sector/industry classification
- Peer financials
- Peer valuation
- Peer growth
- Peer price performance
- Supplier/customer data
- Segment revenue
- Geographic revenue
- Industry KPIs

Granular signals:

- Peer-relative P/E
- Peer-relative EV/EBITDA
- Peer-relative revenue growth
- Peer-relative margin
- Peer-relative ROIC
- Peer-relative earnings revisions
- Peer-relative momentum
- Industry momentum
- Sector breadth
- Market share trend
- Customer concentration risk
- Supplier concentration risk
- Input cost exposure
- Competitive pricing pressure
- Segment-level growth

System role:

- Prevents wrong comparisons.
- Helps avoid buying a cheap company in a collapsing industry.
- Improves target price with peer-based multiples.

Failure modes:

- Sector labels can be too broad.
- Peer groups can be cherry-picked.
- Supply-chain relationships can change quickly.

Source anchors:

- Industry momentum: https://onlinelibrary.wiley.com/doi/pdf/10.1111/0022-1082.00146
- MSCI factor models: https://www.msci.com/our-solutions/factor-investing/factor-models

---

### 5.14 Macro, regime, and factor timing

Question: "What environment are we in?"

Raw inputs:

- Fed funds rate
- Yield curve
- Treasury yields
- Inflation
- Unemployment
- PMI/ISM
- GDP nowcasts
- Credit spreads
- VIX
- Dollar index
- Oil
- Commodities
- Sector ETFs
- Factor ETF returns
- Market breadth

Granular signals:

- Rate level
- Rate change
- Yield curve slope
- Inflation surprise
- Credit spread widening
- VIX regime
- Dollar strength
- Oil shock
- Commodity input cost shock
- Liquidity regime
- Risk-on/risk-off score
- Market breadth
- Sector rotation
- Factor momentum
- Value regime
- Growth regime
- Low-vol regime
- Quality defensive regime

System role:

- Adjusts factor weights.
- Changes required alert gap.
- Explains why good stock-level signals may fail temporarily.

Failure modes:

- Macro signals are slow and noisy.
- Regime models can overfit.
- Factor timing is difficult and should be conservative.

Source anchors:

- MSCI Barra models and regime/risk signals: https://www.msci.com/our-solutions/factor-investing/factor-models
- Invesco factor investing overview: https://www.invesco.com/apac/en/institutional/insights/factor-investing/foundational-concepts-for-understanding-factor-investing.html
- Dynamic factor allocation with regimes: https://arxiv.org/abs/2410.14841

---

### 5.15 Positioning, ownership, and flows

Question: "Who owns it, who is forced to buy/sell, and is positioning crowded?"

Raw inputs:

- Institutional ownership
- 13F filings
- Insider transactions
- Short interest
- Borrow fee
- ETF holdings
- Fund flows
- Index membership
- Float
- Buybacks
- Share issuance

Granular signals:

- Insider open-market purchases
- Insider purchase cluster
- Insider sale cluster
- Insider trade size relative to holdings
- Opportunistic versus routine insider trades
- Institutional ownership change
- Hedge fund ownership change
- Concentrated-holder risk
- Short interest / float
- Days to cover
- Borrow fee
- Short-interest change
- ETF flow exposure
- Mutual fund flow exposure
- Index inclusion/deletion pressure
- Buyback pace
- Secondary offering risk
- Lockup expiration

System role:

- Detects crowded long/short risk.
- Helps explain why price diverges from target.
- Can identify squeeze or forced-selling situations.

Failure modes:

- 13F data is delayed.
- Insider sales are often noise.
- Short interest can be bearish information or squeeze fuel.
- Fund-flow data may be indirect.

Source anchors:

- Insider trading informativeness: https://www.nber.org/papers/w6656
- Opportunistic insider trades: https://www.nber.org/papers/w16454
- Short interest and stock returns: https://www.nber.org/papers/w10434
- Mutual fund flows and returns: https://www.nber.org/papers/w11526

---

### 5.16 Options-implied signals

Question: "What is the options market implying about risk, direction, and event moves?"

Raw inputs:

- Implied volatility
- Realized volatility
- Option volume
- Open interest
- Put/call volume
- Put/call open interest
- Skew
- Term structure
- Strikes and expiries
- Earnings implied move

Granular signals:

- IV rank
- IV percentile
- IV minus realized volatility
- Term structure slope
- Put skew
- Call skew
- Risk reversal
- Put/call volume ratio
- Put/call open interest ratio
- Option volume imbalance
- Unusual option activity
- Implied earnings move
- Implied probability distribution
- Gamma exposure approximation
- Volatility crush risk

System role:

- Adds market-implied uncertainty.
- Can detect informed trading before events.
- Can widen/narrow alert thresholds.

Failure modes:

- Options are noisy and affected by hedging flows.
- Many stocks have illiquid options.
- High IV may mean opportunity or danger.

Source anchors:

- Option volume imbalance as predictor: https://arxiv.org/abs/2201.09319
- Call-put implied volatility spreads: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1640322
- Implied volatility overview: https://en.wikipedia.org/wiki/Implied_volatility
- Risk reversal overview: https://en.wikipedia.org/wiki/Risk_reversal

---

### 5.17 Alternative data

Question: "Can we observe business momentum before financial statements?"

Raw inputs:

- Web traffic
- App downloads
- Monthly active users
- Daily active users
- Search trends
- Credit/debit card transactions
- Email receipts
- Geolocation / foot traffic
- Satellite imagery
- Job postings
- Product prices
- Reviews and ratings
- Shipping/import data
- Patent filings
- Government contracts
- App rankings
- Ad spend

Granular signals:

- Website visit growth
- Unique visitor growth
- Bounce rate
- Visit duration
- Conversion proxy
- Search interest trend
- App download trend
- App active-user trend
- App ranking change
- Credit-card sales nowcast
- Foot-traffic growth
- Store-level traffic
- Price scraping inflation/discounting
- Review volume and rating
- Hiring growth
- Layoff signal
- Import shipment growth
- Satellite parking-lot utilization
- Patent velocity
- Government contract awards

System role:

- Nowcasts fundamentals before earnings.
- Useful for consumer, software, e-commerce, travel, restaurants, retail, gaming, autos, and platform companies.

Failure modes:

- Expensive data.
- Vendor methodology changes.
- Coverage gaps.
- Correlation without causation.
- Privacy/compliance constraints.
- Web traffic may not equal revenue.

Source anchors:

- Similarweb alternative data platform: https://www.similarweb.com/corp/stocks/alternative-data/
- Similarweb alternative data guide: https://www.similarweb.com/blog/investor/asset-research/what-is-alternative-data/
- LSEG alternative data: https://www.lseg.com/en/data-analytics/financial-data/alternative-data
- Alternative data overview: https://en.wikipedia.org/wiki/Alternative_data_%28finance%29

---

### 5.18 Governance, legal, accounting, and ESG risk

Question: "Could non-operating risk break the thesis?"

Raw inputs:

- Board composition
- Insider ownership
- Executive compensation
- Related-party transactions
- Auditor changes
- Restatements
- SEC letters
- Litigation
- Regulatory investigations
- ESG controversies
- Cyber incidents
- Labor issues
- Sanctions exposure

Granular signals:

- Auditor resignation
- Financial restatement
- Late filing
- Material weakness
- Insider pledge risk
- Related-party transaction flag
- Governance score
- Dual-class voting risk
- Litigation severity
- Regulatory risk score
- ESG controversy severity
- Cyber incident flag
- Labor strike risk
- Sanction/geopolitical exposure

System role:

- Reduces confidence.
- Widens band.
- Can prevent false "cheap" alerts.

Failure modes:

- Hard to quantify.
- Text extraction and entity mapping can be messy.
- Some risks are binary and sudden.

---

### 5.19 Asset-specific modules

Generic factors are not enough for every sector. Add custom modules.

Banks:

- Net interest margin
- Deposit beta
- Loan growth
- Non-performing loans
- Charge-offs
- Loan-loss reserves
- CET1 ratio
- Tangible book value
- Duration of securities book

Insurers:

- Combined ratio
- Loss ratio
- Expense ratio
- Reserve development
- Investment portfolio yield
- Catastrophe exposure

REITs:

- FFO / AFFO
- Net asset value
- Cap rate
- Occupancy
- Same-store NOI
- Lease duration
- Debt maturity

Energy:

- Oil/gas price sensitivity
- Reserve life
- Production growth
- Lifting cost
- Decline rate
- Hedging book
- Free cash flow at strip price

Biotech/pharma:

- Pipeline stage
- Trial readout date
- Probability of success
- Addressable market
- Patent cliff
- FDA/PDUFA date
- Cash runway

Semiconductors:

- ASP trend
- Inventory days
- Utilization
- Book-to-bill
- Wafer starts
- WFE/capex cycle
- Customer concentration
- Export-control risk

SaaS/software:

- ARR growth
- Net retention
- Gross retention
- CAC payback
- Rule of 40
- Gross margin
- RPO/backlog
- Seat expansion
- Churn
- SBC dilution

Consumer/retail:

- Same-store sales
- Traffic
- Basket size
- Inventory growth
- Markdown risk
- Store count
- Loyalty data
- Search/web/app traffic

Industrials:

- Backlog
- Book-to-bill
- Capacity utilization
- Input-cost spread
- Order cancellations
- PMI sensitivity

Mining/materials:

- Commodity price sensitivity
- Production volume
- Cash cost
- Reserve grade
- Capex intensity
- Country risk

Crypto/digital assets:

- Network activity
- Active addresses
- Transaction volume
- Fees
- Hash rate/staking
- Exchange flows
- Stablecoin liquidity
- Funding rates
- Open interest
- Token unlocks

---

## 6. Model types for prediction

For your use case, prediction should usually mean "expected forward return" or "relative rank", not raw price.

Useful targets:

- 5-day forward return
- 20-day forward return
- 60-day forward return
- 3-month forward excess return versus sector
- 12-month forward return to fair value
- Probability of outperforming sector
- Probability current price reaches target range
- Quantile targets: q10/q50/q90 future return

Simple baseline models:

- Equal-weight composite score
- Z-score weighted factor model
- Linear regression
- Ridge regression
- Lasso / Elastic Net

Stronger tabular models:

- LightGBM
- XGBoost
- CatBoost
- Random Forest

Ranking-focused models:

- Cross-sectional rank model
- Learning-to-rank
- Pairwise/listwise ranker
- RankIC-optimized model

Uncertainty models:

- Quantile regression
- Bayesian regression
- Conformal prediction
- Ensemble dispersion
- Scenario valuation

Deep learning / advanced:

- MLP
- LSTM/GRU
- Temporal Fusion Transformer
- Graph neural networks for supply-chain/sector links
- LLM/NLP for filings, calls, news, and social posts

Practical recommendation:

Start with:

```text
baseline composite score
+ Ridge regression
+ LightGBM rank/regression model
+ quantile model for bands
```

Do not begin with a complex deep model unless the data pipeline is already clean.

Source anchors:

- Qlib model documentation: https://qlib.readthedocs.io/en/stable/component/model.html
- Qlib data handler Alpha158: https://qlib.readthedocs.io/en/latest/component/data.html?highlight=alpha158
- Open Source Asset Pricing: https://www.openassetpricing.com/
- Federal Reserve OSAP paper page: https://www.federalreserve.gov/econres/feds/open-source-cross-sectional-asset-pricing.htm
- Alphalens: https://quantopian.github.io/alphalens/
- Cross-sectional return prediction with ML: https://www.sciencedirect.com/science/article/pii/S0165188923001318

---

## 7. How to combine signals

Do not throw everything into one score immediately. Use a layered combination.

### Layer A: eligibility

Hard filters:

- Enough trading history
- Enough liquidity
- Valid sector
- Fresh fundamentals
- No stale quote
- No broken corporate action

### Layer B: target price

Blend valuation engines:

```text
target_dcf
target_peer_multiple
target_historical_multiple
target_reverse_dcf_reasonable_case
```

Example:

```text
base_target =
  0.35 * dcf_target
  + 0.35 * peer_multiple_target
  + 0.20 * historical_multiple_target
  + 0.10 * analyst_consensus_target_adjusted
```

Weights should depend on sector. DCF may matter more for stable cash-flow businesses; peer multiples may matter more for cyclical or high-growth companies.

### Layer C: alpha confirmation

Signals that confirm convergence:

- Momentum
- Earnings revisions
- Sentiment change
- Catalyst timing
- Industry momentum
- Insider buying
- Short squeeze setup

### Layer D: confidence and risk

Signals that modify band width:

- Volatility
- Analyst dispersion
- Estimate dispersion
- Leverage
- Liquidity
- Event risk
- Governance/accounting risk

### Layer E: alert rule

```text
required_gap =
  base_required_gap
  + uncertainty_penalty
  + liquidity_penalty
  + event_risk_penalty
  - catalyst_bonus
  - high_confidence_bonus
```

Bullish alert:

```text
upside_to_base > required_gap
and current_price < target_low
and alpha_confirmation_score > 60
and confidence_score > 60
and risk_filter_passes
```

Bearish alert:

```text
downside_to_base < -required_gap
and current_price > target_high
and negative_revision_or_momentum_confirmation
and risk_filter_passes
```

---

## 8. Validation checklist

Before trusting any signal:

1. Point-in-time data only.
2. Use actual publish/availability dates, not fiscal period dates.
3. Avoid survivorship bias.
4. Adjust prices correctly for splits/dividends.
5. Winsorize outliers.
6. Rank within sector or industry when appropriate.
7. Neutralize sector, market cap, and beta when testing pure alpha.
8. Test IC and RankIC.
9. Test quantile monotonicity.
10. Test long-short spread.
11. Test turnover.
12. Test transaction costs.
13. Test by market regime.
14. Test by sector.
15. Test by market-cap bucket.
16. Test signal decay by horizon.
17. Test signal correlation with existing signals.
18. Remove redundant signals.
19. Run walk-forward validation.
20. Use purged windows around labels.
21. Check calibration if predicting probabilities.
22. Check interval coverage if predicting target bands.
23. Run ablations: remove one signal family at a time.
24. Monitor live drift.
25. Keep an audit log for every alert.

Core validation metrics:

- IC
- RankIC
- ICIR
- Hit rate
- Precision at top decile
- Quantile spread
- Sharpe
- Max drawdown
- Turnover
- Capacity
- Coverage
- Missing rate
- Feature drift
- Prediction drift
- Alert precision
- Alert false-positive rate

Source anchors:

- Alphalens docs: https://quantopian.github.io/alphalens/
- Qlib docs: https://qlib.readthedocs.io/en/stable/component/model.html
- Open Source Asset Pricing: https://www.openassetpricing.com/
- Publication bias / factor zoo discussion: https://arxiv.org/abs/2209.13623

---

## 9. What should be in Version 1

Do not build all 20 layers at once. Build the minimum system that is expandable.

### V1 data

- Ticker
- Price
- Market cap
- Sector
- Volume / dollar volume
- Financial statements
- Valuation ratios
- Analyst estimates if available
- Earnings dates
- Price history
- Basic news/social sentiment if available

### V1 signals

1. Valuation:
   - forward P/E
   - EV/EBITDA
   - P/FCF
   - sector-relative valuation
   - historical own-multiple valuation

2. Quality:
   - ROE
   - ROIC
   - gross margin
   - operating margin
   - FCF margin
   - leverage
   - accruals

3. Growth:
   - revenue growth
   - EPS growth
   - forward revenue growth
   - forward EPS growth
   - growth acceleration/deceleration

4. Revisions:
   - EPS revision 1m/3m
   - revenue revision 1m/3m
   - target price revision
   - revision breadth

5. Momentum:
   - 3m return
   - 6m return
   - 12m minus 1m return
   - 52-week-high distance
   - sector-relative return

6. Sentiment/news:
   - news sentiment
   - news volume
   - social mention velocity
   - social bullish/bearish ratio

7. Risk/band:
   - realized volatility
   - beta
   - analyst dispersion
   - liquidity
   - earnings within 10 days flag

8. Alert:
   - target range
   - current gap
   - confidence score
   - reason codes
   - stale data check

### V1 alert example

```text
Ticker: ABC
Current price: 84.20
Base target: 109.00
Fair-value range: 98.00 - 120.00
Upside to base: +29.5%
Upside to lower band: +16.4%
Required alert gap: +14.0%
Signal: bullish divergence

Main reasons:
- valuation is cheap versus sector and own history
- quality score is above sector median
- EPS estimates revised up over 3 months
- price momentum is positive versus sector
- news sentiment improved after earnings

Main risks:
- high realized volatility widens band
- target-price dispersion is high
- next earnings date is close
```

---

## 10. Wider range of signal families to consider later

Add these after V1 is working:

- Options skew and unusual option activity
- Short interest and borrow fee
- Insider open-market purchase clusters
- ETF/fund flow pressure
- 13F ownership changes
- Web/app traffic
- Search trends
- Credit-card/revenue nowcasts
- Foot traffic
- Job postings
- Product price scraping
- App rankings
- Patent filings
- Supply-chain graph signals
- Earnings call transcript tone
- Filing risk-language changes
- Macro factor regime
- Sector breadth and factor rotation
- Accounting manipulation risk
- Governance/legal/regulatory risk
- Asset-specific KPIs

---

## 11. Source map

Core factor frameworks:

- Morningstar investment factors: https://www.morningstar.com/investing-terms/investment-factor
- Morningstar Factor Profile: https://www.morningstar.com/products/factor-profile
- MSCI factor indexes: https://www.msci.com/indexes/factor-indexes/msci-factor-indexes
- MSCI Barra equity factor models: https://www.msci.com/our-solutions/factor-investing/factor-models
- BlackRock equity factor exposures: https://www.blackrock.com/us/financial-professionals/tools/factor-box-methodology
- Stockopedia StockRanks: https://www.stockopedia.com/stockranks/
- Factor-Based methodology: https://factorbased.com/rankings/methodology
- S&P Global Alpha Signals: https://www.spglobal.com/market-intelligence/en/solutions/products/quantitative-equity-data-alpha-signals
- Quantpedia factor investing: https://quantpedia.com/strategy-tags/factor-investing/

Academic/data foundations:

- Open Source Asset Pricing: https://www.openassetpricing.com/
- Federal Reserve OSAP page: https://www.federalreserve.gov/econres/feds/open-source-cross-sectional-asset-pricing.htm
- WorldQuant 101 Formulaic Alphas: https://arxiv.org/abs/1601.00991
- Qlib paper: https://arxiv.org/abs/2009.11189
- Qlib data docs: https://qlib.readthedocs.io/en/latest/component/data.html?highlight=alpha158
- Qlib model docs: https://qlib.readthedocs.io/en/stable/component/model.html
- Alphalens: https://quantopian.github.io/alphalens/

Chinese quant platforms and factor taxonomies:

- RiceQuant factor system: https://www.ricequant.com/doc/quant/factor-system
- JoinQuant factor library: https://www.joinquant.com/view/factorlib/list
- JoinQuant data page: https://www.joinquant.com/data
- FactorHub: https://factorhub.cn/
- BigQuant dynamic multi-factor article: https://bigquant.com/square/paper/53e52f5e-6c52-48e1-94df-5a22dcdd88fd
- BigQuant Alpha101: https://bigquant.com/square/paper/dc96259a-a077-40b3-9894-0dd80af070f4
- BigQuant Alpha158 data: https://bigquant.com/data/datasources/cn_stock_factors_alpha_158

Valuation and analyst signals:

- Morningstar moat and fair value methodology: https://www.morningstar.com/business/insights/blog/markets/equity-economic-moat-ratings
- Morningstar fair value glossary: https://admainnew.morningstar.com/webhelp/glossary_definitions/stocks/stocksglossary_Morningstar_Fair_Value.html
- LSEG StarMine analyst revisions: https://www.lseg.com/en/data-analytics/financial-data/analytics/quantitative-analytics/starmine-analyst-revisions-models
- LSEG SmartEstimates: https://www.lseg.com/en/data-analytics/financial-data/analytics/quantitative-analytics/starmine-smartestimates
- Analyst target price dispersion: https://www.sciencedirect.com/science/article/pii/S106294082100022X
- Analyst target accuracy: https://www.tandfonline.com/doi/abs/10.1080/15427560.2024.2368151

Momentum, quality, volatility:

- Jegadeesh and Titman momentum: https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1993.tb04702.x
- Industry momentum: https://onlinelibrary.wiley.com/doi/pdf/10.1111/0022-1082.00146
- AQR Quality Minus Junk: https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk
- Betting Against Beta: https://www.nber.org/papers/w16601

Sentiment and alternative data:

- MSCI News Sentiment: https://www.msci.com/research-and-insights/paper/introducing-news-sentiment-a-systematic-equity-strategy-factor
- LSEG media sentiment: https://www.lseg.com/en/data-analytics/resources/white-paper/the-value-of-alternative-data-and-media-sentiment
- RavenPack factor investing with sentiment: https://www.ravenpack.com/research/equity-factor-investing-enhanced-with-news-earnings-call-transcripts/
- Similarweb alternative data: https://www.similarweb.com/blog/investor/asset-research/what-is-alternative-data/
- Similarweb investor platform: https://www.similarweb.com/corp/stocks/alternative-data/
- LSEG alternative data: https://www.lseg.com/en/data-analytics/financial-data/alternative-data

Positioning, flows, options:

- Insider trades: https://www.nber.org/papers/w6656
- Opportunistic insider trades: https://www.nber.org/papers/w16454
- Short interest: https://www.nber.org/papers/w10434
- Mutual fund flows: https://www.nber.org/papers/w11526
- Option volume imbalance: https://arxiv.org/abs/2201.09319
- Call-put implied volatility spreads: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1640322

---

## 12. The shortest useful takeaway

The exhaustive component list for your target-price divergence system is:

```text
data quality
+ valuation/fair value
+ quality/profitability
+ growth
+ balance sheet
+ cash flow/capital allocation
+ analyst revisions/earnings surprise
+ price momentum/reversal
+ volume/liquidity
+ volatility/beta/uncertainty
+ news/social/text sentiment
+ catalysts/events
+ sector/peer/supply-chain context
+ macro/regime
+ positioning/ownership/flows
+ options-implied signals
+ alternative data
+ governance/legal/accounting risk
+ asset-specific KPIs
+ validation/model health
+ alert logic/explanation
```

The teaching model:

```text
valuation gives the target
quality/growth/revisions decide whether the target is believable
momentum/sentiment/catalysts decide whether price may move now
volatility/liquidity/dispersion decide how wide the band must be
validation decides whether the signal deserves to exist
```

