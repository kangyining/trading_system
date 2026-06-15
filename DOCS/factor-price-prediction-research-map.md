# Factor / price prediction research map

Checked online on 2026-06-05. This file focuses on price/return prediction from factors, not order execution.

Important framing: most professional factor research does **not** try to predict the raw future price level. It usually predicts one of these:

| Target | Meaning | Why it is used |
|---|---|---|
| Forward return | `return[t+1:t+h]` for a horizon like 1 day, 5 days, 21 days, or 1 month | Directly connected to investment payoff. |
| Cross-sectional rank | Which stocks should outperform other stocks over the next horizon | Often more stable than exact return prediction. |
| Direction/class | Up/down, outperform/underperform, top/bottom quantile | Useful when prediction magnitude is noisy. |
| Residual/abnormal return | Future return after removing market/sector/style exposure | Tries to isolate stock-specific alpha. |
| Quantile/distribution | Prediction interval or tail risk, not only point estimate | Useful when uncertainty matters. |

## Best first reads

| Priority | Resource | Why it matters |
|---|---|---|
| 1 | [Empirical Asset Pricing via Machine Learning - Gu, Kelly, Xiu](https://academic.oup.com/rfs/article/33/5/2223/5758276) | Core paper for ML on stock-return prediction. Compares OLS, penalized regressions, trees, boosted trees, and neural nets on firm characteristics. |
| 2 | [NBER page for Empirical Asset Pricing via Machine Learning](https://www.nber.org/papers/w25398) | Easier entry point and citation page for the same work. |
| 3 | [101 Formulaic Alphas - arXiv](https://arxiv.org/abs/1601.00991) | Famous WorldQuant-style formulaic alpha paper. Useful as a factor-engineering idea bank, but do not assume the alphas still work. |
| 4 | [Microsoft Qlib docs](https://qlib.readthedocs.io/en/stable/introduction/introduction.html) | Practical AI quant platform for factor features, model training, prediction scores, backtesting, and analysis. |
| 5 | [Qlib Forecast Model docs](https://qlib.readthedocs.io/en/stable/component/model.html) | Directly relevant: forecast models produce prediction scores for stocks; includes LightGBM, MLP, LSTM examples. |
| 6 | [Qlib LightGBM + Alpha158 example](https://github.com/microsoft/qlib/blob/main/examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml) | Concrete template: Alpha158 factors + LightGBM + train/valid/test split + prediction score. |
| 7 | [Alphalens GitHub](https://github.com/quantopian/alphalens) | Standard open-source factor evaluation toolkit. Focuses on predictive alpha factors, IC, quantile returns, turnover. |
| 8 | [Alphalens tutorial / tear sheet walkthrough](https://notebook.community/quantopian/alphalens/alphalens/examples/tear_sheet_walk_through) | Good practical introduction to measuring a factor's predictive value without first building a whole trading system. |
| 9 | [Open Source Cross-Sectional Asset Pricing - Federal Reserve](https://www.federalreserve.gov/econres/feds/open-source-cross-sectional-asset-pricing.htm) | Large open dataset/codebase reproducing hundreds of published cross-sectional stock-return predictors. |
| 10 | [Global Factor Data - Jensen, Kelly, Pedersen](https://jkpfactors.com/data) | Large global factor dataset with 153 characteristics across many countries. Good for serious factor research. |

## Prediction factor families

### 1. Price-volume / technical / formulaic alpha factors

These are built from OHLCV data: open, high, low, close, volume, VWAP, returns, rolling ranks, correlations, volatility, drawdowns, moving averages, and intraday features.

| Resource | Notes |
|---|---|
| [101 Formulaic Alphas - arXiv](https://arxiv.org/abs/1601.00991) | Classic formulaic alpha library. Treat as feature ideas, not deployable signals. |
| [WorldQuant Alpha 101 explained](https://coriva.eu.org/en/alpha101-overview/) | Readable taxonomy and operator explanation for Alpha101. |
| [BigQuant - WorldQuant Alpha101 因子复现及因子分析](https://bigquant.com/wiki/doc/Gl3vglHyog) | Chinese implementation/analysis of Alpha101 on Chinese stocks. |
| [BigQuant - Alpha158 因子构建公式](https://bigquant.com/wiki/doc/nODcNAKYPJ) | Chinese Alpha158 formula reference: trend, volatility, price position, volume, price-volume relation. |
| [BigQuant - Qlib 官方 Alpha158 全因子](https://bigquant.com/data/datasources/cn_stock_factors_alpha_158) | Data-source page describing Alpha158 as a baseline technical-factor set for ML feature engineering. |
| [Qlib Alpha158 / Alpha360 usage](https://qlib.readthedocs.io/en/latest/component/data.html?highlight=alpha158) | Practical Qlib data-handler docs. |
| [AlphaFormer - End-to-End Symbolic Regression of Alpha Factors](https://proceedings.mlr.press/v328/huang26a.html) | Newer 2026 paper on Transformer-generated alpha factors. Advanced. |

Best algorithms here:

| Algorithm | Use |
|---|---|
| Single-factor IC / RankIC | First test whether a factor ranks stocks in the same direction as future returns. |
| Linear regression / ridge / lasso | Good baseline; less likely to hallucinate structure. |
| LightGBM / XGBoost / CatBoost | Strong default for tabular factor features and nonlinear interactions. |
| Learning-to-rank | Best when the actual task is ranking stocks, not predicting exact returns. |
| Symbolic regression / genetic programming / LLM alpha mining | Useful for factor discovery, but high overfitting risk. |

### 2. Fundamental / firm-characteristic factors

These include valuation, size, profitability, quality, investment, leverage, payout, accruals, asset growth, earnings quality, analyst revisions, and balance-sheet variables.

| Resource | Notes |
|---|---|
| [Open Source Cross-Sectional Asset Pricing - Federal Reserve](https://www.federalreserve.gov/econres/feds/open-source-cross-sectional-asset-pricing.htm) | One of the most useful sources for firm-characteristic predictor definitions and replication code. |
| [Global Factor Data](https://jkpfactors.com/data) | Download factor returns and characteristic-managed portfolios for 153 characteristics. |
| [MSCI - Foundations of Factor Investing](https://www.msci.com/research-and-insights/paper/foundations-of-factor-investing) | High-level factor overview: value, low size, low volatility, high yield, quality, momentum. |
| [AQR - Factor Momentum Everywhere](https://www.aqr.com/insights/research/working-paper/factor-momentum-everywhere) | Factor timing / factor momentum. More about factor premia than single-stock prediction, but useful. |
| [Searching the Factor Zoo](https://www.researchgate.net/publication/323695870_Searching_the_Factor_Zoo) | Factor-zoo pruning and predictor relevance. |
| [Machine Learning for Stock Prediction Based on Fundamental Analysis](https://arxiv.org/abs/2202.05702) | Uses quarterly financial data and ML models such as FNN, random forest, ANFIS. |
| [Improving Factor-Based Quantitative Investing by Forecasting Company Fundamentals](https://arxiv.org/abs/1711.04837) | Interesting angle: predict future fundamentals first, then use factor investing on forecasted fundamentals. |

Best algorithms here:

| Algorithm | Use |
|---|---|
| Fama-MacBeth / cross-sectional regression | Classic expected-return modeling from characteristics. |
| Ridge / lasso / elastic net | Handles many correlated accounting factors. |
| Partial least squares / PCA / IPCA | Extracts lower-dimensional latent structure from many characteristics. |
| Random forest / gradient boosting / LightGBM | Strong for nonlinear interactions and missing/dirty tabular data. |
| Neural nets | Can work with enough data, but validation must be strict. |

### 3. Momentum, reversal, and trend factors

These predict from past returns and market state. Common examples: 1-month reversal, 12-1 month momentum, industry momentum, residual momentum, short-term reversal, volatility-adjusted momentum, factor momentum.

| Resource | Notes |
|---|---|
| [AQR - Value and Momentum Everywhere](https://research.cbs.dk/en/publications/value-and-momentum-everywhere-2) | Classic cross-asset evidence for value and momentum. |
| [AQR - Factor Momentum Everywhere](https://www.aqr.com/insights/research/working-paper/factor-momentum-everywhere) | Tests momentum in factor premia themselves. |
| [Learning to Rank: Enhancing Momentum Strategies Across Asset Classes](https://papers.ssrn.com/sol3/Delivery.cfm/5255258.pdf?abstractid=5255258&mirid=1) | Learning-to-rank applied to cross-sectional momentum. |
| [Building Cross-Sectional Systematic Strategies by Learning to Rank](https://arxiv.org/abs/2012.07149) | Directly relevant: pairwise/listwise ranking models can improve cross-sectional stock/asset ranking. |
| [Constructing long-short stock portfolio with a listwise learn-to-rank algorithm](https://arxiv.org/abs/2104.12484) | Instead of predicting return value, predicts ranked stock lists. |

Best algorithms here:

| Algorithm | Use |
|---|---|
| Rank-based factor sort | Baseline for momentum/reversal. |
| Logistic regression/classifier | Predict outperform/underperform rather than exact return. |
| LightGBM ranker / LambdaMART | Natural fit for top-decile stock selection. |
| Regime-aware models | Momentum and reversal often flip by horizon/regime. |

### 4. News, sentiment, NLP, and alternative data factors

These use text or alternative information: news sentiment, earnings call transcripts, social media, analyst text, supply-chain data, option-implied data, search trends, web traffic, job postings, satellite/card data if available.

| Resource | Notes |
|---|---|
| [News versus Sentiment: Predicting Stock Returns from News Stories](https://colab.ws/articles/10.17016%2Ffeds.2016.048) | Uses a large news dataset to test return prediction. |
| [Stock-specific sentiment and return predictability](https://www.tandfonline.com/doi/abs/10.1080/14697688.2020.1736314) | Stock-specific news sentiment and future returns. |
| [Using Financial News Sentiment for Stock Price Direction Prediction](https://www.mdpi.com/1687594) | News sentiment for S&P 500 direction prediction. |
| [Predicting Returns with Text Data - Xiu et al.](https://dachxiu.chicagobooth.edu/download/Sentiment.pdf) | More serious text-mining/return-predictability paper. |
| [BERT-based Financial Sentiment Index and LSTM-based Stock Return Predictability](https://arxiv.org/abs/1906.09024) | BERT sentiment + LSTM, including Hong Kong/Weibo context. |
| [Stock Movement Prediction with Financial News using BERT](https://arxiv.org/abs/2107.08721) | Short-term movement prediction from headlines. |
| [BigQuant - 财经新闻挖掘与股票策略构建](https://bigquant.com/square/paper/9281ad54-9607-49c5-892b-da5af7e18d73) | Chinese BigQuant report on extracting hidden/sentiment factors from Chinese financial news. |

Best algorithms here:

| Algorithm | Use |
|---|---|
| Dictionary sentiment | Baseline: Loughran-McDonald, Chinese finance lexicons, polarity/uncertainty. |
| FinBERT / BERT embeddings | Convert text into sentiment or dense features. |
| Gradient boosting on text-derived factors | Often stronger and simpler than end-to-end deep models. |
| LSTM/Transformer over event sequences | Useful if you have enough timestamped events. |
| LLM scoring | Useful for structured extraction and qualitative signal scoring; validate like any other factor. |

### 5. Cross-stock relationship / graph factors

These model stocks as connected nodes: industry links, supply-chain links, ownership, co-news/co-mention, return correlation, price similarity, customer-supplier relationships, index membership, and dynamic latent graphs.

| Resource | Notes |
|---|---|
| [Stock ranking prediction using graph aggregation network](https://www.sciencedirect.com/science/article/abs/pii/S0020025523008216) | Graph aggregation using stock relationships and price information. |
| [Graph learning on financial networks from firm-characteristic similarity](https://link.springer.com/article/10.1007/s41109-025-00755-2) | GNNs for monthly U.S. stock return prediction using characteristic-similarity networks. |
| [GRU-PFG: Extract Inter-Stock Correlation from Stock Factors with GNN](https://arxiv.org/abs/2411.18997) | Projects stock factors into graph structure; combines GRU with graph learning. |
| [GCNET: graph-based prediction of stock price movement](https://arxiv.org/abs/2203.11091) | Influence-network framework for stock movement prediction. |
| [Higher-order Graph Attention Network for Stock Selection](https://arxiv.org/abs/2306.15526) | Predicts stock return ranks with higher-order graph attention. |
| [Temporal and Heterogeneous Graph Neural Network for Financial Time Series Prediction](https://arxiv.org/abs/2305.08740) | Dynamic relation graph and temporal prediction. |
| [Exploiting Supply Chain Interdependencies for Stock Return Prediction](https://ideas.repec.org/p/arx/papers/2303.09406.html) | Supply-chain graph + temporal neural network. |

Best algorithms here:

| Algorithm | Use |
|---|---|
| Correlation / similarity graph features | Simple baseline before neural graphs. |
| Graph convolution / graph attention | Learns spillovers across related stocks. |
| Temporal GNN / Graph-LSTM | Adds time dynamics to relationship graphs. |
| Heterogeneous graph transformer | For multiple edge types such as supplier, sector, co-news, ownership. |

### 6. LLM / symbolic alpha mining

This is newer and riskier. The useful role is not "ask an LLM what stock goes up tomorrow." The useful role is: generate candidate factor formulas, map natural-language hypotheses into executable features, extract structured text signals, or improve formulaic alpha search.

| Resource | Notes |
|---|---|
| [Alpha-GPT: Human-AI Interactive Alpha Mining](https://arxiv.org/abs/2308.00016) | Human-AI alpha mining paradigm. |
| [Navigating the Alpha Jungle: LLM + MCTS for formulaic factor mining](https://arxiv.org/abs/2505.11122) | LLM-guided Monte Carlo tree search for factor formulas. |
| [AlphaBench - Benchmarking LLMs in Formulaic Alpha Factor Mining](https://alphabench.cc/) | Benchmark for LLM alpha-factor mining workflow. |
| [Chain-of-Alpha](https://arxiv.org/abs/2508.06312) | LLM chain framework for generating and optimizing alpha factors. |
| [QuantaAlpha](https://arxiv.org/abs/2602.07085) | Evolutionary framework for LLM-driven alpha mining. |
| [Harnessing ChatGPT for predictive financial factor generation](https://www.sciencedirect.com/science/article/pii/S0890838924002877) | GPT-generated financial statement factors. |
| [Sentiment-Aware Stock Price Prediction with Transformer and LLM-Generated Formulaic Alpha](https://arxiv.org/abs/2508.04975) | LLM-generated alphas used as model features with Transformer/LSTM/TCN/SVR/RF. |

Best algorithms here:

| Algorithm | Use |
|---|---|
| LLM + rule validator | Generate only formulas that compile and use allowed fields/operators. |
| Symbolic regression | Search formula space with constraints. |
| MCTS / evolutionary search | Explore formula variants. |
| Strict out-of-sample IC testing | Mandatory, because factor mining is extremely prone to false discovery. |

## Algorithm families for factor prediction

| Family | Examples | Good for | Cautions |
|---|---|---|---|
| Single-factor statistics | IC, RankIC, ICIR, t-stat, decile spread | Screening individual factors | Can overfit if you test hundreds without correction. |
| Linear models | OLS, Fama-MacBeth, ridge, lasso, elastic net | Interpretable baselines and high-dimensional factor sets | Miss nonlinear interactions. |
| Dimension reduction | PCA, PLS, IPCA, autoencoders | Compressing large factor libraries | Harder to interpret; unstable if data shifts. |
| Tree ensembles | Random forest, XGBoost, LightGBM, CatBoost | Tabular price/fundamental factors; nonlinear interactions | Easy to leak information through rolling features and preprocessing. |
| Learning-to-rank | RankNet, LambdaRank, LambdaMART, listwise rankers | Stock selection where top/bottom ranking matters | Needs careful ranking labels and cross-sectional evaluation. |
| Deep sequence models | MLP, LSTM, GRU, TCN, Transformer, TFT, TabNet | Long sequence patterns, many features, temporal dependencies | Many "price prediction" demos just learn a lagged/smoothed price. |
| Graph models | GCN, GAT, temporal GNN, heterogeneous graph transformer | Spillovers across related stocks | Needs reliable graph data; otherwise the graph can add noise. |
| Probabilistic/uncertainty models | Gaussian process, quantile regression, Bayesian neural nets | Prediction uncertainty, risk-aware expected returns | More complex; harder to scale across large universes. |
| LLM/symbolic factor mining | Alpha-GPT, MCTS, evolutionary alpha search | Generating candidate factors and text-derived signals | Very high false-discovery risk. |

## Evaluation metrics for prediction

For factor prediction, I would prioritize these over headline "accuracy":

| Metric | Meaning |
|---|---|
| IC | Correlation between factor score/prediction and future returns. |
| Rank IC | Spearman rank correlation between factor rank and future return rank. Often more useful for stock selection. |
| ICIR | Mean IC divided by IC standard deviation; stability of predictive skill. |
| Quantile return spread | Future return of top factor bucket minus bottom factor bucket. |
| Hit rate by quantile | How often top-ranked names beat bottom-ranked names. |
| Cross-sectional R2 | How much return variation the model explains across stocks. Usually small in finance. |
| Factor decay | IC by horizon: 1D, 5D, 10D, 21D, etc. |
| Turnover | Even if not focused on execution, high turnover can mean the prediction is too fragile to use. |
| Neutralized IC | IC after industry, beta, size, or country neutralization. Helps separate real alpha from style exposure. |

Useful docs:

| Resource | Notes |
|---|---|
| [Alphalens API docs](https://quantopian.github.io/alphalens/alphalens.html) | Factor returns, IC, mean IC, quantile analysis. |
| [Alphalens tutorial](https://notebook.community/quantopian/alphalens/alphalens/examples/alphalens_tutorial_on_quantopian) | Explains IC and factor predictivity. |
| [RiceQuant 因子研究](https://www.ricequant.com/doc/quant/factor-system) | Chinese docs for factor creation, IC analysis, return analysis. |
| [JoinQuant - 单因子分析之 IC/ICIR 和 T-test](https://joinquant.com/community/post/detailMobile?postId=38494) | Chinese intro to single-factor IC/ICIR and hypothesis testing. |
| [BigQuant - 量价因子有效性与相关性问题探讨](https://bigquant.com/square/paper/345f9392-5e6d-4a10-ba1a-0f6439237d2b) | Chinese factor validity analysis using RankIC, ICIR, layered returns. |
| [TEJ - Analyzing Factor Performance with Alphalens](https://www.tejwin.com/en/insight/analyzing-factor-performance-with-alphalens-price-and-volume-factors/) | Alphalens-style price/volume factor analysis. |

## Chinese resources focused on factor prediction

| Resource | Why it is useful |
|---|---|
| [BigQuant - Alpha158 因子构建公式](https://bigquant.com/wiki/doc/nODcNAKYPJ) | Clear Chinese formula list for Qlib Alpha158 factors. |
| [BigQuant - Alpha101 因子复现及因子分析](https://bigquant.com/wiki/doc/Gl3vglHyog) | Chinese Alpha101 implementation and factor analysis. |
| [BigQuant - 机器学习与因子（一）：特征工程算法测评](https://bigquant.com/square/paper/d7e33756-cd86-433c-95f9-0a12244d016c) | Compares ML models for short-term A-share return prediction using factors; mentions LightGBM/XGBoost strength. |
| [BigQuant - 机器学习模型在因子选股上的比较分析](https://bigquant.com/square/paper/70de90be-0a36-45b7-9b5a-5be690ac6c67) | Compares logistic regression, SVM, random forest, XGBoost, DNN using 156 stock factors. |
| [BigQuant - 股票多因子系列（三）：机器学习在多因子组合中的应用](https://bigquant.com/square/paper/08670bb2-0955-4fa8-b076-ffe4346fcb48) | Supervised ML for multi-factor portfolio prediction. |
| [RiceQuant 因子研究](https://www.ricequant.com/doc/quant/factor-system) | Factor creation/evaluation workflow: IC, returns, audits, collaboration. |
| [基于机器学习的股票收益预测与投资组合研究](https://image.hanspub.org/Html/58-1701515_84872.htm) | Chinese paper combining ML and multi-factor model; tests RF, SVM, XGBoost. |
| [人工智能与中国股票市场——基于机器学习预测的投资组合量化研究](https://journal03.magtech.org.cn/Jweb_gyjsjj/CN/10.3969/j.issn.1004-910X.2022.08.011) | Uses 20 value/technical/momentum/sentiment reversal indicators and 8 ML algorithms for Chinese stock-return prediction. |
| [基于机器学习的资产收益率预测研究综述](https://www.sciengine.com/parse/pdf/1003-207X/0E40DD2897AF46CAB9578F365A46C290.pdf?attname=0E40DD2897AF46CAB9578F365A46C290.pdf) | Chinese survey of ML asset-return prediction. |
| [新浪财经 / 信达金工 - 用 DeepSeek 优化价量因子](https://finance.sina.com.cn/roll/2025-03-21/doc-ineqmfqm9578881.shtml) | Recent Chinese article on using DeepSeek to improve price-volume factors and RankIC/ICIR. Treat carefully, but useful for ideas. |
| [BigQuant - Quantformer](https://mf.bigquant.com/square/paper/c1be3650-032f-4a07-aad4-aee0fc9568c1) | Chinese report on Transformer-style stock trend prediction with quantitative factors and sentiment transfer. |

## Recommended practical path

If the goal is to build a prediction-first trading research system, I would start with these experiments:

1. **Single-factor lab**
   - Build Alpha101 / Alpha158 style features.
   - Measure IC, RankIC, ICIR, factor decay, and quantile returns.
   - Do this before ML.

2. **Baseline ML model**
   - Label: 5-day or 21-day forward return.
   - Features: Alpha158 + simple fundamentals if available.
   - Model: ridge regression and LightGBM.
   - Output: prediction score/rank, not raw price.

3. **Cross-sectional ranker**
   - Use the model to rank stocks each rebalance date.
   - Compare regression-to-rank vs a learning-to-rank model.
   - Evaluate with RankIC and top-minus-bottom decile spread.

4. **Fundamental factor model**
   - Use OSAP/JKP-style firm characteristics.
   - Start monthly, because fundamentals update slowly.
   - Models: elastic net, random forest, LightGBM.

5. **Text/sentiment add-on**
   - Extract event-level sentiment from headlines/news/filings.
   - Aggregate by stock and horizon.
   - Add to the baseline model and test incremental IC.

6. **Graph model only after the basics work**
   - Add industry/supply-chain/correlation graph features.
   - Compare against simple sector-neutralized LightGBM first.

7. **LLM alpha mining as idea generation**
   - Let LLMs propose factor formulas.
   - Enforce allowed operators/fields.
   - Reject anything that fails point-in-time, out-of-sample, and multiple-testing checks.

## What I would avoid early

| Avoid | Why |
|---|---|
| Raw next-price prediction with LSTM | Many demos just learn a smoothed/lagged price, not a usable forecast. |
| Accuracy-only up/down classifiers | A 53% classifier can be useless if it predicts low-payoff moves or has bad calibration. |
| Huge factor mining without multiple-testing correction | You will find "good" factors by chance. |
| Training on adjusted/final data without point-in-time controls | Corporate actions, restatements, and survivorship can leak future information. |
| Mixing all stocks/time periods randomly in train/test split | Financial data needs time-based or purged/walk-forward validation. |
| Optimizing only Sharpe/backtest PnL | For prediction research, inspect IC, RankIC, factor decay, stability, and feature importance first. |

## Best starting algorithm stack

My conservative starting stack:

| Layer | Choice |
|---|---|
| Factor set | Alpha158 / Alpha101 subset + basic fundamental factors |
| Preprocessing | Winsorize, cross-sectional z-score or rank, industry/size neutralization |
| Baseline model | Ridge / elastic net |
| Main model | LightGBM regression or ranking |
| Validation | Walk-forward train/valid/test; no random split |
| Primary metric | RankIC + top-minus-bottom quantile spread |
| Interpretability | Feature importance, SHAP with caution, ablation tests |
| Robustness | Different horizons, regimes, universes, sectors, and markets |

