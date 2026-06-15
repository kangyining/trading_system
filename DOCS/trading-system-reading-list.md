# 交易系统 reading list

Checked online on 2026-06-05. I treated "交易系统" as a broad trading-system topic: rules, risk, position sizing, backtesting, overfitting, execution, and research-to-live architecture.

This is not investment advice. It is a reading map for building a disciplined and testable system.

## How to read this

Suggested order:

1. Learn the system lifecycle: hypothesis, rules, backtest, paper trade, live trade, monitor, retire.
2. Learn risk first: position sizing, stop logic, drawdown controls, daily loss limits, kill switches.
3. Learn backtesting traps: costs, slippage, look-ahead bias, survivorship bias, data snooping, overfitting.
4. Study architecture: data, strategy, portfolio, risk, order management, execution, reconciliation.
5. Only then study specific strategies such as trend following, mean reversion, breakout, factor rotation, or AI/RL.

## Best first reads

| Priority | Language | Resource | Why it is useful |
|---|---|---|---|
| 1 | Chinese | [量化交易系统架构: 研究、回测、模拟、实盘四套环境](https://quant67.com/post/quant/27-trading-system-arch/27-trading-system-arch.html) | Probably the best Chinese starting point I found for system architecture. It frames the real problem as keeping research, backtest, paper trading, and live trading consistent. |
| 2 | English | [QuantStart - Beginner's Guide to Quantitative Trading](https://www.quantstart.com/articles/Beginners-Guide-to-Quantitative-Trading/) | Strong general foundation: strategy identification, backtesting, execution, and risk management. |
| 3 | English | [QuantStart - Should You Build Your Own Backtester?](https://www.quantstart.com/articles/Should-You-Build-Your-Own-Backtester/) | Very useful for thinking about strategy, portfolio/order management, risk, position sizing, and execution as separate modules. |
| 4 | English | [TradingStrategy.ai - Backtesting & Research Methodology](https://tradingstrategy.ai/docs/learn/backtesting.html) | Good modern overview of backtest self-deception, walk-forward validation, parameter diversification, and robustness testing. |
| 5 | Chinese | [BigQuant - BigTrader 量化交易引擎（回测）](https://bigquant.com/wiki/doc/bigtrader-hftrade-3gG2rg4jBd) | Practical Chinese platform documentation showing how a professional backtest engine thinks about data, simulation, matching, and live-like behavior. |
| 6 | English | [QuantInsti - Position Sizing Strategies and Techniques](https://blog.quantinsti.com/position-sizing/) | Practical risk/position sizing article with formulas and common mistakes. |
| 7 | Chinese | [RiceQuant - RQAlphaPlus 用户指南](https://www.ricequant.com/doc/rqalpha-plus/doc/index-rqalphaplus) | Useful Chinese event-driven framework docs. Good for seeing how a strategy framework handles data, risk, matching, account state, and reporting. |
| 8 | English | [QuantConnect - Algorithm Framework Overview](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview) | Excellent modular architecture: universe selection, alpha, portfolio construction, risk management, execution. |
| 9 | English | [NautilusTrader Documentation](https://nautilustrader.io/docs/latest/) | Production-grade event-driven architecture with emphasis on research-to-live parity. Best for engineering discipline. |
| 10 | Chinese | [vn.py - 基于 Python 的开源交易平台开发框架](https://www.vnpy.org/) | Important Chinese open-source trading framework. Useful if you care about domestic broker/exchange connectivity and real trading infrastructure. |

## English resources

### Foundations and workflow

| Resource | Best use |
|---|---|
| [QuantStart - Beginner's Guide to Quantitative Trading](https://www.quantstart.com/articles/Beginners-Guide-to-Quantitative-Trading/) | Big-picture workflow for quant/systematic trading. |
| [QuantStart - Event-Driven Backtesting with Python, Part I](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I) | Why event-driven systems are more realistic than simple vectorized backtests, and what modules are needed. |
| [QuantStart - Should You Build Your Own Backtester?](https://www.quantstart.com/articles/Should-You-Build-Your-Own-Backtester/) | Deciding between simple backtests, framework backtests, and a custom event-driven engine. |
| [QSTrader Introduction](https://www.quantstart.com/qstrader/introduction/) | Example of an open-source event-driven research/backtest system with portfolio and risk mechanics. |
| [QuantConnect - Algorithm Framework Overview](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview) | Clean mental model for separating alpha, portfolio construction, risk, and execution. |
| [NautilusTrader - Concepts Overview](https://nautilustrader.io/docs/latest/concepts/overview) | Architecture for backtest, sandbox/paper trading, and live trading under a common core. |
| [NautilusTrader - Live Trading](https://nautilustrader.io/docs/latest/concepts/live/) | What changes when a strategy goes live: configuration, reconciliation, venue state, execution reality. |

### Backtesting, validation, and overfitting

| Resource | Best use |
|---|---|
| [TradingStrategy.ai - Backtesting & Research Methodology](https://tradingstrategy.ai/docs/learn/backtesting.html) | Practical and theoretical checklist for avoiding false confidence in backtests. |
| [Quantpedia - Quantopian paper on in-sample vs out-of-sample performance](https://quantpedia.com/quantopians-academic-paper-about-in-vs-out-of-sample-performance-of-trading-alg/) | Read for evidence that high backtest Sharpe alone predicts out-of-sample performance poorly. |
| [The Probability of Backtest Overfitting - eScholarship](https://escholarship.org/uc/item/4w1110bb) | Core paper behind PBO and combinatorially symmetric cross-validation. Advanced but important. |
| [The Deflated Sharpe Ratio - Bailey and Lopez de Prado PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) | Adjusts Sharpe interpretation for multiple testing, non-normal returns, and selection bias. |
| [Ernie Chan - Backtesting and its Pitfalls PDF](https://www.epchan.com/wp-content/uploads/2022/04/Backtesting-and-its-Pitfalls.pdf) | Practitioner-friendly list of common backtesting errors. |
| [Implementation Risk in Portfolio Backtesting - arXiv](https://arxiv.org/abs/2603.20319) | Recent paper on how different backtesting engines can diverge even for the same logical strategy. |
| [Backtesting - Wikipedia](https://en.wikipedia.org/wiki/Backtesting) | Quick reference only. Useful for definitions and bias terms, not enough by itself. |

### Risk, position sizing, and survival

| Resource | Best use |
|---|---|
| [QuantInsti - Position Sizing Strategies and Techniques](https://blog.quantinsti.com/position-sizing/) | Clear introduction to fixed amount, percentage risk, Kelly-style ideas, and behavioral mistakes. |
| [Britannica Money - Calculating Position Size](https://www.britannica.com/money/calculating-position-size) | Beginner-friendly explanation of risk per trade, stop distance, and position size math. |
| [Van Tharp Institute - Why Size Really Does Matter](https://vantharpinstitute.com/why-size-really-does-matter-by-van-k-tharp-ph-d-2/) | Classic position sizing mindset: system returns depend heavily on sizing rules. |
| [Van Tharp Institute - Position Sizing Calculator](https://vantharpinstitute.com/tools/position-sizing-calculator/) | Useful simple calculator for translating stop distance and risk percent into share/contract quantity. |
| [TradeZella - Risk Management in Trading, 2026 Guide](https://www.tradezella.com/blog/risk-management-trading) | Recent retail-practical guide covering position sizing, stop placement, session limits, and drawdown controls. |
| [AlgoStorm - Trading Risk Management: Position Sizing Guide](https://algostorm.com/risk-management/) | Broad guide covering sizing methods, risk/reward, drawdown, and asset-specific considerations. |

### Frameworks and tools

| Resource | Best use |
|---|---|
| [Backtrader](https://www.backtrader.com/) | Popular Python framework for backtesting and live-trading style strategy development. |
| [Backtrader - Sizers](https://www.backtrader.com/docu/sizers/sizers/) | Read this specifically for how a framework separates signal logic from position sizing. |
| [VectorBT Pro](https://vectorbt.pro/) | High-speed vectorized research and parameter exploration. Best for broad research sweeps, less for execution-realistic simulation. |
| [Quantpedia - How it Works](https://quantpedia.com/how-it-works/) | Good lens for judging whether a strategy writeup is implementable, robust, and not a black box. |
| [QuantConnect LEAN / Algorithm Framework docs](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview) | Practical path if you want cloud/backtest/live with broker integrations. |

### AI and reinforcement learning, read with caution

| Resource | Best use |
|---|---|
| [FinRL: Deep Reinforcement Learning Framework to Automate Trading](https://arxiv.org/abs/2111.09395) | Popular open-source full-stack AI/RL framework paper. Good for architecture and reproducibility ideas. |
| [Deep Reinforcement Learning in Quantitative Algorithmic Trading: A Review](https://arxiv.org/abs/2106.00123) | Useful caution: many DRL papers are proof-of-concept with unrealistic settings or weak live validation. |
| [Backtesting Trading Strategies with GAN to Avoid Overfitting](https://arxiv.org/abs/2209.04895) | Advanced idea: test strategy robustness against generated price paths, not just one historical path. |
| [Improving Backtesting Robustness with Boltzmann Machines and GANs](https://arxiv.org/abs/2007.04838) | Another advanced robustness angle for synthetic scenarios. |

## Chinese resources

### System architecture and research-to-live

| Resource | Best use |
|---|---|
| [量化交易系统架构: 研究、回测、模拟、实盘四套环境](https://quant67.com/post/quant/27-trading-system-arch/27-trading-system-arch.html) | Best Chinese conceptual article I found. Focuses on consistency across research, backtest, paper, and live. |
| [量化交易系统开发实录（一）: 项目启动与架构设计的五个关键决策](https://milome.github.io/blog/series-quant-trading/quant-trading-dev-series-part1/) | Practical engineering decisions for building your own system. |
| [从零到一: 手把手构建专业量化交易系统的全流程指南](https://cloud.baidu.com/article/4465980) | Broad Chinese overview of data, strategy, backtest, risk, and deployment modules. |
| [Awesome-QuantDev-Learn](https://github.com/0voice/Awesome-QuantDev-Learn) | GitHub roadmap for quant development: data, strategy, backtest engine, live deployment, monitoring. |
| [Panda QuantFlow 全量源码深度解析文档](https://www.pandaai.online/community/article/551) | Architecture/code-analysis style resource for a modular Python quant system. |
| [Panda Backtest 模块深度分析](https://www.pandaai.online/community/article/544) | More specific look at event-driven backtest, matching, risk, and result statistics. |

### Chinese platform/framework docs

| Resource | Best use |
|---|---|
| [RiceQuant - RQAlphaPlus 用户指南](https://www.ricequant.com/doc/rqalpha-plus/doc/index-rqalphaplus) | Event-driven abstraction and full-process strategy framework. |
| [RiceQuant - 平台简介](https://www.ricequant.com/doc/quant/) | Quick overview of RiceQuant's data, backtest, and simulation platform. |
| [BigQuant - BigTrader 量化交易引擎（回测）](https://bigquant.com/wiki/doc/bigtrader-hftrade-3gG2rg4jBd) | Professional backtest engine concepts: time-driven playback, matching, costs, market rules. |
| [vn.py 官网](https://www.vnpy.org/) | Major Chinese Python open-source trading framework. |
| [vn.py 教程](https://www.vnpy.org/pages/tutorial.html) | Entry point for tutorials and practical platform learning. |
| [FMZ 发明者量化平台回测说明](https://www.fmz.com/digest-topic/4009) | Good explanation of bar/tick backtesting modes and practical simulation details. |
| [FMZ 回测系统模式](https://www.fmz.com/user-guide/%E5%9B%9E%E6%B5%8B%E7%B3%BB%E7%BB%9F/%E5%9B%9E%E6%B5%8B%E7%B3%BB%E7%BB%9F%E6%A8%A1%E5%BC%8F) | Platform docs explaining real-tick and simulated-tick backtest behavior. |

### Risk control, execution, and live/backtest gaps

| Resource | Best use |
|---|---|
| [BigQuant - 探析: 量化交易策略回测绩效与实盘表现不一致](https://bigquant.com/wiki/doc/muD2XDiJRG) | Good Chinese discussion of why backtests often outperform live results. |
| [BigQuant - 高频策略落地关键: 数据接口选型对回测-实盘拟合度的影响](https://bigquant.com/wiki/doc/5dw14N7xQT) | Useful if your strategy is intraday/high-frequency or depends heavily on live data latency and quality. |
| [BigQuant - 量化开发者必学: 订单簿撮合逻辑与实盘成交优化](https://bigquant.com/wiki/doc/OeT9llian0) | Execution realism: order book, matching, fills, and why backtest fills can lie. |
| [BigQuant - 外汇实时行情接入: 对量化回测与实盘一致性的影响](https://bigquant.com/wiki/doc/RuJMLwdtJ9) | Market data architecture and why data feed design affects research reproducibility. |
| [腾讯云 - Rust 量化风控模块设计: 动态仓位管理与回撤控制](https://cloud.tencent.com/developer/article/2659194?policyId=1003) | Concrete risk module design: position sizing, drawdown control, volatility adjustment. |
| [掘金 - Python 量化交易系统实战: 订单执行与仓位管理模块](https://juejin.cn/post/7617051223863771179) | Code-oriented article for order and position modules. Treat as implementation inspiration, not gospel. |

### Strategy concepts and entry-level trading-system thinking

| Resource | Best use |
|---|---|
| [Gate 学院 - 如何构建交易系统](https://www.gate.com/zh/learn/articles/how-to-build-a-trading-system/8275) | Beginner-friendly personal trading system article: entries, exits, timeframe, position management. |
| [趋势跟踪完整指南](https://www.fxkiller.com/zh/education/trend-following) | Useful for trend-following concepts and the idea of rule-based entries/exits. |
| [东方财富 - 期货投资者必看: 6 大类 20+ 经典交易系统全解析](https://caifuhao.eastmoney.com/news/20250519081915703327680) | Broad catalog of classic futures/trading-system styles. Use as idea inventory, then validate independently. |
| [PBO 算法在量化交易中的应用 PDF](https://pdf.hanspub.org/aam20230400000_48265777.pdf) | Chinese academic-style material on probability of backtest overfitting. |
| [自动交易系统 - 中文维基百科](https://zh.wikipedia.org/wiki/%E8%87%AA%E5%8A%A8%E4%BA%A4%E6%98%93%E7%B3%BB%E7%BB%9F) | Reference only. Useful for terminology and known automated-trading failure examples. |

## My practical takeaway

A useful trading system should be documented as rules and controls, not just a signal:

| Module | Questions the system must answer |
|---|---|
| Universe | What can be traded, and when is an instrument excluded? |
| Data | What exact data is used, with what timestamps, adjustments, and survivorship rules? |
| Signal | What creates a long/short/flat decision? |
| Position sizing | How much is traded, based on account equity, volatility, stop distance, correlation, and max exposure? |
| Risk | What vetoes or reduces a trade? What is the max daily loss, max drawdown, max leverage, max sector exposure? |
| Execution | Market, limit, TWAP/VWAP, close/open auction, rebalance timing, order retries, partial fills? |
| Backtest assumptions | Costs, slippage, borrow, liquidity, latency, fill model, corporate actions, T+1 rules where relevant. |
| Validation | Out-of-sample, walk-forward, PBO/DSR, Monte Carlo trade reshuffling, regime tests, sensitivity tests. |
| Live monitoring | Reconciliation, stale data checks, broker rejects, alerts, kill switch, post-trade attribution. |
| Retirement rule | What evidence proves the strategy is broken or should be reduced? |

## Shortlist to actually study first

If you only read 8 items first:

1. quant67 四套环境 article.
2. QuantStart beginner guide.
3. QuantStart "Should You Build Your Own Backtester?"
4. TradingStrategy.ai backtesting methodology.
5. QuantInsti position sizing.
6. QuantConnect Algorithm Framework.
7. BigQuant backtest/live mismatch article.
8. NautilusTrader docs overview.

