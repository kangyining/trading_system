# Target-price signal system design

Checked online on 2026-06-05. This note reframes the system around the actual end-goal:

> Estimate a fair/target price, compare it with market price, and alert when the divergence is large enough to matter.

This is not investment advice. It is a system-design note for research and monitoring.

## Core idea

A useful signal should not be just:

`target price = 123`

It should be:

| Field | Meaning |
|---|---|
| Current price | Latest tradable/reference price. |
| Base target price | Central fair-value estimate. |
| Low/high fair-value band | Uncertainty range around the target. |
| Time horizon | 1 week, 1 month, 3 months, 12 months, etc. |
| Gap | `(target - current_price) / current_price`. |
| Confidence | How reliable the signal currently is. |
| Reason codes | Which factors explain the target and the alert. |
| Alert threshold | How large the gap must be after volatility/model-error buffers. |
| Signal action | Watch, bullish divergence, bearish divergence, avoid, stale data. |

## Target price should be a range

Use a target range instead of a single number:

| Estimate | Example method |
|---|---|
| Low target | Conservative assumptions, lower multiple, slower growth, higher discount rate. |
| Base target | Main model estimate. |
| High target | Optimistic assumptions, stronger growth/revisions, lower risk premium. |

This avoids false precision. Many analyst target-price and valuation studies treat target prices as noisy but potentially informative, especially when combined with revisions and other factors.

Useful sources:

- [Stock valuation - target price definition](https://en.wikipedia.org/wiki/Stock_valuation)
- [What Drives Target Price Forecasts and Their Investment Value?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1785640)
- [Target price forecasts: Fundamental and non-fundamental factors](https://digitalcommons.pepperdine.edu/graziadiowps/19/)
- [The asymmetric mispricing information in analysts' target prices](https://link.springer.com/article/10.1007/s11142-022-09730-z)

## Your current factor list

You listed:

1. Fundamentals
2. Momentum
3. Sentiment, especially social media

That is a good start, but incomplete for a target-price divergence system.

## What is missing

### 1. Valuation / fair-value anchor

This is the most important missing bucket because your goal explicitly needs a target price.

Fundamentals say how good the business is. Valuation says what it is worth at today's price.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Relative valuation | P/E, EV/EBITDA, P/S, P/B, FCF yield versus sector/history. |
| Absolute valuation | DCF, dividend discount, residual income, owner earnings. |
| Implied growth | What growth rate is the current price already assuming? |
| Peer multiple gap | Stock versus direct comparable companies. |
| Historical multiple gap | Current multiple versus own 3/5/10-year range. |
| Sum-of-parts | Useful for conglomerates or multi-segment businesses. |

Signal role:

`valuation_target = fair_multiple * forward_metric`

or:

`valuation_target = DCF_base_value_per_share`

Sources:

- [Stock valuation](https://en.wikipedia.org/wiki/Stock_valuation)
- [MSCI - Foundations of Factor Investing](https://www.msci.com/research-and-insights/paper/foundations-of-factor-investing)
- [Factor investing](https://en.wikipedia.org/wiki/Factor_investing)

### 2. Quality / financial strength

Fundamentals are broad. You should split out quality because the same valuation gap means different things for a strong business versus a fragile one.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Profitability | ROE, ROIC, gross margin, operating margin. |
| Earnings quality | Accruals, cash conversion, free cash flow quality. |
| Balance-sheet strength | Debt/EBITDA, interest coverage, current ratio. |
| Stability | Revenue stability, margin stability, earnings volatility. |
| Bankruptcy/fragility | Altman Z-score, Piotroski F-score, Beneish M-score. |

Signal role:

- Raises confidence in undervaluation signals.
- Lowers target or widens uncertainty band for fragile firms.

Sources:

- [Stockopedia StockRanks: Quality, Value, Momentum](https://www.stockopedia.com/stockranks/)
- [Factor-Based Rankings Methodology](https://factorbased.com/rankings/methodology)

### 3. Growth and forward expectations

A company can look expensive but still be cheap if forward growth is underestimated. This should be separate from raw fundamentals.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Revenue growth | Historical and expected growth. |
| EPS/FCF growth | Forward and trailing growth. |
| Margin expansion | Operating leverage, gross margin trend. |
| TAM/product cycle | Harder to quantify, but useful as structured notes. |
| Growth durability | Consistency and length of runway. |

Signal role:

`target_price = forward_EPS * justified_PE`

where `justified_PE` depends on growth, margins, quality, and risk.

Sources:

- [Stockopedia StockRanks](https://www.stockopedia.com/stockranks/)
- [Seeking Alpha Quant Ratings factor grades FAQ](https://help.seekingalpha.com/migration/premium/quant-ratings-and-factor-grades-faq)

### 4. Analyst estimates, revisions, and target-price dispersion

This is different from social-media sentiment. Estimate revisions are often more directly connected to target-price changes and future returns.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| EPS revision momentum | 1M/3M change in next-year EPS estimates. |
| Revenue revision momentum | Upgrades/downgrades to forward revenue. |
| Target-price revision | Consensus target moving up/down. |
| Recommendation change | Buy/hold/sell upgrades and downgrades. |
| Dispersion | Wide target-price disagreement = higher uncertainty. |
| Surprise history | Earnings beats/misses and post-earnings drift. |

Signal role:

- Positive revisions can confirm that the target should move up.
- High dispersion should widen the target range and reduce confidence.

Sources:

- [MSCI - Introducing Analyst Sentiment](https://www.msci.com/research-and-insights/paper/introducing-analyst-sentiment-a-systematic-equity-strategy-factor)
- [Analysts' Earnings Forecast, Recommendation and Target Price Revisions](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1883819)
- [Dispersion in analysts' target prices and stock returns](https://www.sciencedirect.com/science/article/pii/S106294082100022X)

### 5. Volatility / risk / uncertainty

A 20% gap is huge for a stable utility and ordinary for a speculative biotech. Alerts should be volatility-adjusted.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Realized volatility | 20D/60D/252D volatility. |
| Beta | Market sensitivity. |
| Idiosyncratic volatility | Stock-specific volatility after market/sector. |
| Drawdown risk | Max drawdown, distance from highs. |
| Model error | Historical target error by stock/sector/model. |
| Implied volatility | Options market expected move, if available. |

Signal role:

Use a dynamic threshold:

`alert_threshold = max(base_gap, k * volatility_band, model_error_band, cost_buffer)`

Sources:

- [Factor investing - common factors include low volatility and liquidity](https://en.wikipedia.org/wiki/Factor_investing)
- [Morningstar Global Risk Model Methodology](https://www.morningstar.com/content/dam/marketing/shared/Company/Products/Direct_Cloud/RiskModel_Global_Methodology.pdf)

### 6. Liquidity / tradability

Even if you are not focused on execution, liquidity matters because illiquid names can show false gaps and stale prices.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Dollar volume | Price × volume. |
| Bid-ask spread | Wider spread = less reliable signal. |
| Volume trend | Abnormal volume, volume dry-up. |
| Market cap/free float | Size and capacity constraints. |
| Stale price flag | Low trading activity or delayed prints. |

Signal role:

- Do not trigger high-conviction alerts on stale or illiquid prices.
- Require bigger divergence for illiquid names.

Sources:

- [FactorsToday methodology: point-in-time liquidity filtering](https://www.factorstoday.com/about)
- [Factor investing](https://en.wikipedia.org/wiki/Factor_investing)

### 7. Macro / regime / sector context

A target-price gap can persist or expand if the macro regime is hostile.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Market regime | Risk-on/risk-off, trend, volatility regime. |
| Rates | Treasury yields, real rates, credit spreads. |
| Inflation | CPI trend, commodity inputs. |
| FX | Important for exporters, commodity companies, ADRs, Canadian holdings. |
| Sector regime | Sector momentum, sector valuation, industry revisions. |
| Factor regime | Value/momentum/quality currently working or not. |

Signal role:

- Adjust discount rate and multiples.
- Reduce confidence when macro/sector pressure contradicts the valuation signal.

Sources:

- [AQR - Factor Momentum Everywhere](https://www.aqr.com/insights/research/working-paper/factor-momentum-everywhere)
- [Generating Alpha: Hybrid AI system with regime filtering](https://arxiv.org/abs/2601.19504)

### 8. News / event catalysts

Social sentiment is useful, but you also want concrete catalysts.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Earnings date | Upcoming report risk. |
| Guidance changes | Raised/lowered guidance. |
| Product/regulatory events | FDA, approvals, investigations, launches. |
| M&A / buybacks / issuance | Capital actions. |
| Insider transactions | Insider buying/selling. |
| Unusual institutional flow | 13F changes, fund ownership, large block activity. |

Signal role:

- A large divergence without a catalyst can stay large.
- A large divergence with an upcoming catalyst deserves a different alert type.

Sources:

- [News versus Sentiment: Predicting Stock Returns from News Stories](https://colab.ws/articles/10.17016%2Ffeds.2016.048)
- [Predicting Returns with Text Data](https://dachxiu.chicagobooth.edu/download/Sentiment.pdf)

### 9. Options / short interest / positioning

This is optional but valuable, especially for short-term alerts.

Useful subfactors:

| Subfactor | Examples |
|---|---|
| Short interest | Days to cover, short interest change. |
| Borrow cost | Hard-to-borrow signals and squeeze risk. |
| Options skew | Put/call implied volatility skew. |
| Put-call volume | Directional options activity. |
| Implied move | Expected move through earnings/events. |

Signal role:

- Warn when "undervalued" stocks are heavily shorted for a reason.
- Identify squeeze/positioning risk when price diverges from model value.

Sources:

- [Options prices and stock-return prediction evidence](https://www.sciencedirect.com/science/article/pii/S0378426614003616)

## Suggested factor map for your system

I would structure it like this:

| Pillar | Purpose | Examples |
|---|---|---|
| Valuation | Builds target price | DCF, peer multiples, historical multiples, FCF yield. |
| Fundamentals / quality | Tests business strength | ROIC, margins, balance sheet, cash conversion. |
| Growth / revisions | Updates target direction | EPS/revenue revisions, sales growth, margin expansion. |
| Momentum | Measures market confirmation | 1M/3M/6M/12M return, trend, relative strength. |
| Sentiment | Measures crowd/news tone | Social sentiment, news sentiment, analyst sentiment. |
| Risk / volatility | Sizes uncertainty band | Beta, realized vol, implied vol, drawdown. |
| Liquidity | Filters bad alerts | Dollar volume, spread, stale price, free float. |
| Macro / sector regime | Adjusts valuation context | Rates, credit spreads, sector momentum, factor regime. |
| Catalysts / events | Explains timing | Earnings, guidance, product/regulatory events, buybacks. |
| Positioning | Flags squeeze/crowding | Short interest, options skew, institutional flow. |

## Alert logic

A simple alert rule:

```text
gap = (target_price - current_price) / current_price

bullish_alert if:
  gap > required_gap
  and current_price < low_end_of_fair_value_range
  and confidence >= minimum_confidence
  and data_is_fresh
  and liquidity_is_ok

bearish_alert if:
  gap < -required_gap
  and current_price > high_end_of_fair_value_range
  and confidence >= minimum_confidence
  and data_is_fresh
```

Dynamic required gap:

```text
required_gap = max(
  10%,
  1.5 * 60d_volatility_move,
  model_historical_error,
  expected_event_move,
  transaction_cost_and_spread_buffer
)
```

## Signal types

| Signal | Meaning |
|---|---|
| Deep undervaluation | Price is far below fair-value band, with decent confidence. |
| Overvaluation | Price is far above fair-value band. |
| Value trap warning | Cheap valuation but poor quality, negative revisions, weak sentiment. |
| Momentum confirmation | Price momentum agrees with positive target gap. |
| Contrarian setup | Price is weak, target gap is large, fundamentals/revisions remain intact. |
| Broken thesis | Target dropped because fundamentals/revisions/regime changed. |
| Stale/noisy signal | Gap exists, but liquidity/data/model uncertainty is too poor. |

## Practical first version

For version 1, keep it simple:

| Component | Version 1 choice |
|---|---|
| Target price | Blend of relative valuation target + analyst consensus target + simple DCF/earnings model. |
| Confidence | Based on target dispersion, estimate revisions, factor agreement, and model error. |
| Core factors | Valuation, quality, growth/revisions, momentum, sentiment. |
| Filters | Liquidity, volatility, sector, stale data. |
| Alert | Gap larger than dynamic threshold and outside fair-value band. |
| Explanation | Show top 3 reasons for target and top 3 risks. |

## Bottom line

Your list is good, but I would expand it from:

```text
fundamentals + momentum + social sentiment
```

to:

```text
valuation target
+ fundamentals/quality
+ growth/revisions
+ momentum
+ sentiment/news
+ volatility/risk band
+ liquidity filter
+ macro/sector regime
+ catalyst calendar
+ positioning/options/short interest
```

The key missing piece is **not another prediction model**. It is the combination of:

1. A fair-value target,
2. An uncertainty band,
3. A dynamic divergence threshold,
4. A reason-coded alert.

