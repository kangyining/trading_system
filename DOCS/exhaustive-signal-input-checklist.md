# Exhaustive signal input checklist

Created on 2026-06-05.

Goal:

> Build a system that estimates target/fair price, watches current market price, and alerts when price diverges meaningfully from target.

Your current list:

1. Fundamentals
2. Momentum
3. Sentiment, especially social media

Those are useful, but they are only 3 of the required signal families. The biggest missing pieces are:

1. Valuation anchor
2. Growth and estimate revisions
3. Quality and financial strength
4. Risk/uncertainty band
5. Liquidity and data reliability
6. Macro/sector regime
7. Catalysts/events
8. Positioning/flows
9. Model validation and alert calibration

## Master checklist

| Category | Include? | Why it matters for target-price divergence |
|---|---:|---|
| Fundamentals | Already listed | Business economics behind the target price. |
| Momentum | Already listed | Market confirmation or contradiction. |
| Social sentiment | Already listed | Crowd mood, attention, retail pressure. |
| Valuation / fair value | Missing | Needed to create the target price. |
| Growth expectations | Missing | A cheap stock can be bad if growth is falling; an expensive stock can be fair if growth is rising. |
| Analyst estimates / revisions | Missing | Forward EPS/revenue revisions often move target prices before fundamentals are reported. |
| Quality / profitability | Missing | Determines whether a valuation gap is opportunity or value trap. |
| Balance sheet / solvency | Missing | Debt and liquidity risk should lower target or widen band. |
| Cash flow quality | Missing | Accounting earnings are less useful if not converted to cash. |
| Capital allocation | Missing | Buybacks, dilution, M&A, dividends, reinvestment discipline affect per-share value. |
| Risk / volatility | Missing | Determines how large a price gap must be before alerting. |
| Liquidity / tradability | Missing | Stale or illiquid prices create false divergence alerts. |
| Macro regime | Missing | Rates, inflation, credit, FX, and commodities affect discount rates and earnings. |
| Sector / peer context | Missing | Target should be relative to industry economics and peer multiples. |
| Catalysts / event calendar | Missing | Determines timing and whether divergence can close. |
| News sentiment | Missing | More direct than social sentiment for company-specific information. |
| Analyst sentiment | Missing | Separate from social sentiment; includes recommendations, target changes, estimate changes. |
| Options data | Missing | Implied move, skew, put/call, and options volume reveal uncertainty and positioning. |
| Short interest / borrow | Missing | Flags crowded shorts, squeeze risk, and negative informed positioning. |
| Insider transactions | Missing | Insider buying/selling can confirm or contradict valuation gap. |
| Institutional ownership / flows | Missing | 13F changes, ETF flows, fund ownership, block activity. |
| Alternative data | Missing | Web traffic, app downloads, card data, foot traffic, jobs, patents, supply chain. |
| Governance / management | Missing | Bad governance can make cheap stocks stay cheap. |
| Accounting quality / red flags | Missing | Restatements, accruals, auditor issues, aggressive adjustments. |
| Legal / regulatory / ESG risk | Missing | Can dominate target price for banks, pharma, energy, China ADRs, etc. |
| Share structure / dilution | Missing | Options, convertibles, SBC, warrants, dual-class shares affect per-share value. |
| Model confidence / error | Missing | A target needs a confidence score and error band. |
| Data freshness / point-in-time checks | Missing | Prevents look-ahead bias and stale alerts. |
| Alert threshold logic | Missing | Converts valuation gap into actual signal. |

## 1. Valuation / fair-value anchor

This is the most important missing category.

Without valuation, the system can say "good company" or "strong momentum," but it cannot justify a target price.

Subfactors:

| Subfactor | Examples |
|---|---|
| Relative multiples | P/E, forward P/E, PEG, EV/EBITDA, EV/Sales, P/B, P/FCF. |
| Historical valuation | Current multiple vs own 3/5/10-year history. |
| Peer valuation | Current multiple vs direct peers and sector. |
| DCF | Revenue, margin, reinvestment, WACC, terminal growth. |
| Reverse DCF | Growth/margin assumptions implied by current price. |
| Residual income | Useful for banks, insurers, mature firms. |
| Dividend discount | Useful for stable dividend companies. |
| Sum of parts | Segments valued separately. |
| NAV / asset value | REITs, holding companies, resource companies, financials. |
| Liquidation/replacement value | Downside anchor for asset-heavy businesses. |
| Scenario valuation | Bear/base/bull target range. |

For your system:

```text
target_price = weighted_blend(
  dcf_target,
  peer_multiple_target,
  historical_multiple_target,
  analyst_consensus_target,
  reverse_dcf_sanity_check
)
```

## 2. Growth expectations

Growth should be separated from general fundamentals because target price is mostly about **future** cash flows.

Subfactors:

| Subfactor | Examples |
|---|---|
| Revenue growth | 1Y/3Y/5Y historical and forward. |
| EPS growth | Forward EPS CAGR, EPS acceleration. |
| FCF growth | Free cash flow per share growth. |
| Margin expansion | Gross/operating/net margin trend. |
| Unit economics | CAC, LTV, retention, ARPU, same-store sales where relevant. |
| Operating leverage | Revenue growth converting into faster profit growth. |
| TAM / runway | Addressable market and penetration. |
| Product cycle | New product adoption, patent cliffs, refresh cycles. |
| Backlog / bookings | Industrial, software, defense, infrastructure. |
| Commodity/price sensitivity | Oil, metals, agriculture, shipping, airlines. |

For your system:

```text
justified_multiple = f(growth, quality, risk, rates)
```

## 3. Analyst estimates and revisions

This is a major omission. Analyst target prices are noisy, but estimate revisions and target revisions are useful as a signal family.

Subfactors:

| Subfactor | Examples |
|---|---|
| EPS revision momentum | 1M/3M/6M changes in next-year EPS estimates. |
| Revenue revision momentum | 1M/3M/6M changes in sales estimates. |
| EBITDA/FCF revisions | Especially useful outside tech. |
| Target-price revision | Direction and magnitude of analyst target changes. |
| Recommendation revision | Upgrades, downgrades, buy/hold/sell mix. |
| Estimate breadth | Percent of analysts revising up vs down. |
| Estimate dispersion | Disagreement around EPS/revenue forecasts. |
| Target-price dispersion | Disagreement around target prices, useful as uncertainty/risk proxy. |
| Earnings surprise history | Beat/miss trend and post-earnings drift. |
| Guidance gap | Company guidance vs consensus. |

For your system:

```text
revision_score = zscore(eps_revision_3m)
               + zscore(revenue_revision_3m)
               + zscore(target_revision_3m)
               - zscore(estimate_dispersion)
```

## 4. Quality / business strength

Quality tells you whether undervaluation is likely real or a trap.

Subfactors:

| Subfactor | Examples |
|---|---|
| Profitability | ROE, ROA, ROIC, gross profitability, EBITDA margin. |
| Margin stability | Gross/operating margin volatility. |
| Earnings stability | EPS volatility, loss frequency. |
| Cash conversion | FCF/net income, CFO/net income. |
| Accruals | High accruals can signal lower earnings quality. |
| Leverage | Debt/EBITDA, net debt/equity, interest coverage. |
| Liquidity | Current ratio, quick ratio, cash runway. |
| Bankruptcy risk | Altman Z-score, distance to default. |
| Accounting risk | Beneish M-score, restatements, auditor changes. |
| Moat/profit persistence | ROIC persistence, pricing power, churn. |

For your system:

```text
if valuation_gap_positive and quality_score_low:
  signal = "possible value trap"
```

## 5. Balance sheet and capital structure

This deserves its own bucket because target price is per-share value, not just enterprise value.

Subfactors:

| Subfactor | Examples |
|---|---|
| Net debt | Cash minus debt. |
| Debt maturity wall | Near-term maturities. |
| Interest-rate sensitivity | Floating-rate debt, refinancing risk. |
| Preferred equity | Claims senior to common. |
| Minority interest | Enterprise-to-equity bridge. |
| Pension liabilities | Underfunded pensions. |
| Leases | Capitalized lease obligations. |
| Convertibles/warrants | Dilution at higher prices. |
| Stock-based compensation | Ongoing dilution. |
| Buyback capacity | Repurchases can close undervaluation. |
| Share issuance | Dilution can destroy apparent upside. |

## 6. Cash flow and capital allocation

Subfactors:

| Subfactor | Examples |
|---|---|
| FCF yield | Free cash flow / market cap. |
| FCF margin | FCF / revenue. |
| Capex intensity | Maintenance vs growth capex. |
| Working capital | Inventory, receivables, payables changes. |
| Dividend policy | Yield, payout ratio, safety. |
| Buybacks | Repurchase yield, price paid vs intrinsic value. |
| M&A | Deal discipline, integration history. |
| Reinvestment rate | Growth funded internally or externally. |
| ROIC vs WACC | Value creation or destruction. |

## 7. Momentum, expanded

You listed momentum, but it should be split into several types.

Subfactors:

| Subfactor | Examples |
|---|---|
| Relative strength | Stock vs market/sector. |
| 12-1 momentum | 12-month return excluding most recent month. |
| Short-term reversal | 1D/5D/1M reversal. |
| Trend | Moving average slope, price above MA. |
| Breakout / drawdown | 52-week high proximity, breakout from range. |
| Volume-confirmed momentum | Price move with abnormal volume. |
| Earnings momentum | Price trend around earnings. |
| Residual momentum | Momentum after removing market/sector beta. |
| Sector momentum | Sector trend as confirmation. |
| Factor momentum | Whether value, quality, growth, momentum factors are currently working. |

## 8. Sentiment, expanded

Social media is one channel, not the full sentiment layer.

Subfactors:

| Subfactor | Examples |
|---|---|
| Social sentiment | Reddit, X/Twitter, StockTwits, Discord where available. |
| Social attention | Mention volume, acceleration, user breadth. |
| News sentiment | Company news tone, event sentiment. |
| Analyst sentiment | Buy/hold/sell mix, rating changes, target revisions. |
| Earnings-call sentiment | Management tone, Q&A hedging, uncertainty language. |
| Filing sentiment | 10-K/10-Q/8-K risk-language changes. |
| Search interest | Google Trends, Wikipedia views. |
| Employee sentiment | Glassdoor, job reviews, turnover proxy. |
| Customer sentiment | App reviews, product reviews, web reviews. |
| Contrarian sentiment | Excessive optimism/pessimism flags. |

## 9. News and catalysts

Subfactors:

| Subfactor | Examples |
|---|---|
| Earnings calendar | Upcoming report, pre/post earnings windows. |
| Guidance changes | Raise/cut guidance. |
| Product launches | Launch dates, adoption metrics. |
| Regulatory events | FDA, antitrust, rate decisions, approvals. |
| Litigation | Lawsuits, settlements, investigations. |
| M&A | Rumors, definitive deals, break risk. |
| Buybacks/dividends | Announcements, authorization size. |
| Index inclusion/exclusion | S&P, Nasdaq, Russell reconstitution. |
| Spin-offs | Segment value realization. |
| Investor day | New long-term targets. |
| Lockup expiry | Supply overhang. |

For your system:

```text
if abs(gap) is large and catalyst_within_30d:
  alert_priority += 1
```

## 10. Macro and regime

Subfactors:

| Subfactor | Examples |
|---|---|
| Rates | 2Y/10Y yields, real yields. |
| Credit spreads | HY/OAS, investment-grade spreads. |
| Inflation | CPI/PCE trend, commodity inflation. |
| FX | USD, CAD, exposure by revenue/cost geography. |
| Commodities | Oil, gas, copper, gold, agriculture. |
| Market regime | Risk-on/risk-off, VIX, index trend. |
| Liquidity regime | Financial conditions, Fed balance sheet, money supply proxies. |
| Yield curve | Banks, cyclicals, housing. |
| Economic cycle | PMI, unemployment, earnings-cycle stage. |
| Country/geopolitical risk | Tariffs, sanctions, war, local policy. |

For your system:

```text
discount_rate = base_cost_of_equity + rate_adjustment + risk_premium_adjustment
```

## 11. Sector and peer context

Subfactors:

| Subfactor | Examples |
|---|---|
| Sector valuation | Sector multiple vs history. |
| Peer-relative valuation | Company vs closest peers. |
| Sector revisions | Are estimates rising across the industry? |
| Sector momentum | Sector price strength. |
| Industry margins | Normalized margin level. |
| Competitive position | Market share, pricing, unit growth. |
| Supply/demand cycle | Semis, commodities, autos, housing, shipping. |
| Regulatory sensitivity | Banks, utilities, healthcare, defense. |

## 12. Risk, volatility, and uncertainty band

This is mandatory for divergence alerts.

Subfactors:

| Subfactor | Examples |
|---|---|
| Realized volatility | 20D/60D/252D vol. |
| Implied volatility | Options-implied move. |
| Beta | Market beta. |
| Sector beta | Sector sensitivity. |
| Idiosyncratic vol | Stock-specific vol after factor adjustment. |
| Drawdown | Distance from 52-week high, max drawdown. |
| Tail risk | Gap risk, earnings move history. |
| Model error | Historical target forecast error. |
| Estimate dispersion | Forecast disagreement. |
| Target dispersion | Analyst target disagreement. |

For your system:

```text
fair_value_band = [
  target_price - uncertainty_buffer,
  target_price + uncertainty_buffer
]
```

## 13. Liquidity and price reliability

Subfactors:

| Subfactor | Examples |
|---|---|
| Dollar volume | Price x average volume. |
| Bid-ask spread | Wider spread means less reliable mark. |
| Free float | Float-adjusted market cap. |
| Share turnover | Volume / shares outstanding. |
| Stale price | No recent trades, halted, delayed data. |
| Slippage proxy | Spread + volatility + dollar volume. |
| Exchange quality | OTC vs major listing. |
| Corporate action adjustment | Splits, dividends, spinoffs. |

Even if you are not building execution, this protects alerts from garbage input prices.

## 14. Positioning and flows

Subfactors:

| Subfactor | Examples |
|---|---|
| Short interest | Percent float short, days to cover. |
| Short-interest change | Surprise increase/decrease. |
| Borrow fee | Hard-to-borrow pressure. |
| Options skew | Put/call IV skew. |
| Put/call volume | Directional options demand. |
| Options open interest | Crowded strikes, gamma zones. |
| Insider buying/selling | Open-market buys/sells, cluster buys. |
| Institutional ownership | 13F changes, hedge fund ownership. |
| ETF/index flows | Passive buying/selling pressure. |
| Buybacks/issuance | Company as buyer/seller of own stock. |
| Congressional/political trades | Optional and noisy, but may be monitored. |

## 15. Alternative data

This is optional for version 1, but useful later.

Subfactors:

| Subfactor | Examples |
|---|---|
| Web traffic | Similarweb-style visits, conversion proxies. |
| App downloads / usage | Mobile app rank, DAU/MAU proxies. |
| Credit/debit card data | Sales nowcast. |
| Foot traffic | Retail, restaurants, travel. |
| Satellite | Parking lots, oil storage, mining activity. |
| Job postings | Hiring trend, layoffs, expansion. |
| Patents | R&D direction, innovation pipeline. |
| Shipping/imports | Supply chain activity. |
| Pricing data | Web-scraped product prices, discounting. |
| Review data | Product/customer satisfaction. |
| Lobbying / government contracts | Policy-sensitive companies. |

## 16. Governance and management quality

Subfactors:

| Subfactor | Examples |
|---|---|
| Insider ownership | Alignment with shareholders. |
| Management track record | Guidance credibility, capital allocation. |
| Board independence | Governance quality. |
| Executive compensation | Dilution, incentives, performance metrics. |
| Related-party transactions | Governance red flag. |
| Dual-class shares | Control risk. |
| Shareholder friendliness | Buybacks, dividends, transparency. |
| Activist involvement | Potential catalyst or instability. |

## 17. Legal, regulatory, and ESG risk

Subfactors:

| Subfactor | Examples |
|---|---|
| Regulatory exposure | FDA, EPA, SEC, banking regulators, utilities commissions. |
| Litigation | Major lawsuits and settlement risk. |
| Antitrust | Platform companies, M&A deals. |
| Sanctions/export controls | China/semis/defense/energy. |
| Political risk | Tariffs, subsidies, procurement risk. |
| Environmental liabilities | Energy, chemicals, mining. |
| Labor risk | Unions, strikes, safety issues. |
| Reputational controversy | Boycotts, fraud claims, governance scandals. |

## 18. Asset-specific modules

Some industries need custom factors.

| Industry | Extra factors |
|---|---|
| Banks | Net interest margin, deposits, loan growth, credit losses, CET1, duration risk. |
| Insurance | Combined ratio, reserve adequacy, investment portfolio, catastrophe exposure. |
| REITs | AFFO, cap rates, occupancy, lease maturities, NAV discount. |
| Energy | Production, reserves, decline rates, commodity price sensitivity, hedges. |
| Miners | Resource life, grade, cash costs, capex, spot commodity sensitivity. |
| Biotech | Cash runway, pipeline stage, trial data, FDA calendar, dilution risk. |
| SaaS | ARR growth, net retention, CAC payback, churn, rule of 40, SBC. |
| Semis | Inventory cycle, utilization, capex, customer concentration, node/product cycle. |
| Retail | Same-store sales, traffic, inventory, gross margin, promotions. |
| Autos | Deliveries, ASP, incentives, inventory days, residual values. |
| Utilities | Rate base, allowed ROE, regulatory calendar, debt/refinancing. |

## 19. Model health and validation

This is not a market factor, but it is essential for the system.

Subfactors:

| Subfactor | Examples |
|---|---|
| Data freshness | Timestamp of each input. |
| Point-in-time integrity | No future revisions or restated data leaked backward. |
| Source reliability | Source score and fallback source. |
| Missing data | Coverage by ticker/factor. |
| Feature drift | Factor distribution changed vs training history. |
| Model drift | Prediction performance decays. |
| Calibration | Does a 20% upside signal actually behave like 20% upside? |
| Error by sector | Model error differs by industry. |
| Error by market cap | Small caps often noisier. |
| Error by horizon | 1M vs 12M target accuracy. |
| Backtest overfitting | Multiple testing, false discovery, data snooping. |
| Explainability | Top reason codes for target and alert. |

## 20. Alert design

Missing from the original list: the exact rule that converts inputs into alerts.

Required fields:

| Field | Purpose |
|---|---|
| Current price | Reference price. |
| Target price | Central estimate. |
| Target range | Low/base/high fair value. |
| Time horizon | Target period. |
| Gap | `(target - price) / price`. |
| Required gap | Dynamic threshold. |
| Confidence | Probability/quality of signal. |
| Reason codes | What drives the alert. |
| Risk flags | Why the alert may be wrong. |
| Data status | Fresh/stale/missing/conflicting. |

Suggested rule:

```text
gap = (target_price - current_price) / current_price

required_gap = max(
  minimum_gap,
  volatility_buffer,
  model_error_buffer,
  analyst_dispersion_buffer,
  event_risk_buffer,
  liquidity_buffer
)

alert if:
  abs(gap) > required_gap
  and current_price is outside fair_value_band
  and confidence >= threshold
  and data_status == "fresh"
  and liquidity_status != "bad"
```

## Priority order for version 1

If you want the minimum useful system, build these first:

1. Valuation target
2. Target range / uncertainty band
3. Fundamentals and quality
4. Growth and revisions
5. Momentum
6. News/social/analyst sentiment
7. Volatility and liquidity filters
8. Catalyst calendar
9. Alert threshold and reason codes

Then add:

1. Options and short interest
2. Insider and institutional flows
3. Alternative data
4. Graph/peer/supply-chain relationships
5. Industry-specific factor modules

## Source anchors

Useful references used while constructing this checklist:

- Morningstar identifies style, yield, momentum, quality, volatility, liquidity, and size as investment factors: https://www.morningstar.com/investing-terms/investment-factor
- MSCI groups equity factors into value, size, momentum, volatility, quality, yield, growth, and liquidity: https://www.msci.com/research-and-insights/blog-post/creating-a-common-language-for-factor-investing
- MSCI factor indexes include value, low size, low volatility, high yield, quality, momentum, and growth: https://www.msci.com/indexes/factor-indexes/msci-factor-indexes
- Stockopedia combines Quality, Value, and Momentum, with momentum incorporating price and analyst sentiment: https://www.stockopedia.com/stockranks/
- Factor-Based methodology combines value, quality, volatility, technical momentum, growth, and revisions: https://factorbased.com/rankings/methodology
- Morningstar risk model methodology includes liquidity, value-growth, momentum, and volatility definitions: https://www.morningstar.com/content/dam/marketing/shared/Company/Products/Direct_Cloud/RiskModel_Global_Methodology.pdf
- Analyst target-price dispersion can proxy uncertainty/risk: https://www.sciencedirect.com/science/article/pii/S106294082100022X
- Options-implied measures can contain return-predictive information around analyst events: https://www.sciencedirect.com/science/article/pii/S0378426614003616
- Insider trading can contain value-relevant information: https://journals.sagepub.com/doi/10.1177/0148558X0101600206
- Alternative data examples include geolocation, credit card transactions, satellite imagery, and social media: https://en.wikipedia.org/wiki/Alternative_data_%28finance%29

