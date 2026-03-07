CAPITAL STRATA SYSTEMS (CSS)
ARCHITECTURE NOTES
Version: Phase 1 Baseline
Date: 2026-03-07

--------------------------------------------------
1. SYSTEM PURPOSE
--------------------------------------------------

Capital Strata Systems (CSS) is a governance-first automated capital
allocation and trading framework designed to operate with institutional
discipline.

Unlike typical retail trading bots, CSS is structured around:

• Risk governance
• Capital protection
• Autonomous opportunity detection
• Controlled execution
• Full audit trail

The architecture mirrors institutional financial systems where
every trade is treated as a governed financial event rather than
a speculative action.

The system therefore consists of multiple coordinated layers.

--------------------------------------------------
2. CORE DESIGN PRINCIPLES
--------------------------------------------------

CSS is built around five principles:

1. Capital Preservation First  
2. Autonomous Market Observation  
3. Controlled Trade Entry  
4. Trend-Riding Profit Capture  
5. Full System Transparency

The goal is **steady compounding**, not high-frequency speculation.

Target philosophy:

Small consistent gains + strict risk control  
= long-term capital growth.

--------------------------------------------------
3. SYSTEM ARCHITECTURE
--------------------------------------------------

The CSS architecture currently consists of six operational layers.

MARKET DATA LAYER
      ↓
MARKET INTELLIGENCE LAYER
      ↓
STRATEGY / TREND ENGINE
      ↓
POSITION STATE MANAGEMENT
      ↓
TRADE LOGGING
      ↓
PORTFOLIO DASHBOARD

Each layer performs a clearly defined function.

--------------------------------------------------
4. MARKET DATA LAYER
--------------------------------------------------

The Market Data Layer connects to external exchanges and retrieves
live market information.

Current implementation:
Coinbase Advanced Trading API (public endpoints).

Data collected includes:

• current market price
• recent candle data
• asset availability

This layer is deliberately simple and resilient.

Future versions will support:

• OANDA FX feeds
• Futures market feeds
• multi-exchange aggregation

--------------------------------------------------
5. MARKET INTELLIGENCE LAYER
--------------------------------------------------

The Market Intelligence Layer evaluates market conditions.

Current implementation:

tools/css_market_intelligence_v52.py

Responsibilities:

• scan multiple assets
• retrieve live price information
• compute simple momentum score
• rank assets by opportunity strength

Output example:

TOP MOMENTUM ASSETS

1. BTC-USD
2. ETH-USD
3. SOL-USD
4. LINK-USD
5. AVAX-USD

This layer determines **where the engine should focus attention**.

Future upgrades:

• volatility filters
• liquidity filters
• adaptive asset discovery
• multi-timeframe analysis

--------------------------------------------------
6. STRATEGY / TREND ENGINE
--------------------------------------------------

The Strategy Engine is the core of CSS.

Current implementation:

tools/css_autonomous_loop_v54.py

Responsibilities:

• continuously scan ranked assets
• determine entry opportunities
• open paper positions
• manage open trades
• apply trailing stop logic
• maintain capital allocation state

The engine operates in an autonomous loop:

Scan Markets  
↓  
Rank Opportunities  
↓  
Evaluate Entry  
↓  
Enter Position  
↓  
Ride Trend  
↓  
Exit on Reversal

The philosophy is:

ENTER STRONG MOVES  
RIDE THE TREND  
EXIT WHEN TREND WEAKENS

--------------------------------------------------
7. POSITION STATE MANAGEMENT
--------------------------------------------------

CSS maintains a persistent record of open positions.

File:

backend/state/spot_position.json

This ensures that the engine:

• survives restarts
• resumes monitoring open trades
• keeps portfolio state consistent

Stored fields include:

entry_price  
position_size  
timestamp

Future upgrades will add:

• asset symbol
• trailing stop value
• unrealized PnL
• trade metadata

--------------------------------------------------
8. TRADE LOGGING
--------------------------------------------------

Every trade event is recorded.

File:

audit_logs/trades.jsonl

Each record contains:

• timestamp
• asset
• action (BUY / SELL)
• price
• size
• profit / loss

This creates a permanent audit trail and allows:

• performance analysis
• strategy refinement
• compliance reporting

--------------------------------------------------
9. PORTFOLIO DASHBOARD
--------------------------------------------------

The dashboard provides a real-time view of system state.

Current implementation:

tools/css_portfolio_dashboard_v51.py

Displayed information includes:

• current position
• entry price
• position size
• number of trades
• realized profit/loss
• last update timestamp

This dashboard allows operators to observe the system without
interfering with autonomous behaviour.

--------------------------------------------------
10. CAPITAL MANAGEMENT
--------------------------------------------------

Capital is treated as a managed portfolio.

Example configuration:

Starting capital: $400  
Trade allocation: $100 per position

This ensures risk remains contained even if a position fails.

Future upgrades will introduce:

• dynamic position sizing
• drawdown limits
• risk governor integration

--------------------------------------------------
11. CURRENT SYSTEM STATUS
--------------------------------------------------

The following components are operational:

✔ Market scanner  
✔ Momentum ranking  
✔ Autonomous trading loop  
✔ Trailing stop trend logic  
✔ Position persistence  
✔ Trade logging  
✔ Portfolio dashboard  

The system is currently operating in **paper trading mode**.

--------------------------------------------------
12. NEXT DEVELOPMENT PHASE
--------------------------------------------------

The next upgrades planned for CSS include:

v55 — Adaptive Market Discovery  
Automatically detect and rank all tradable Coinbase assets.

v56 — Advanced Entry Filters  
Improve signal quality with stronger entry criteria.

v57 — Enhanced Portfolio Dashboard  
Display live PnL, asset names, and risk metrics.

v58 — Broker Expansion  
Connect CSS to FX markets (OANDA).

--------------------------------------------------
13. LONG TERM VISION
--------------------------------------------------

CSS is intended to evolve into a **governed capital allocation
platform** capable of operating across multiple asset classes:

• cryptocurrencies
• foreign exchange
• futures
• equities

The architecture is deliberately modular to support this expansion.

Ultimately CSS will function as:

An institutional-grade autonomous capital allocation engine.

--------------------------------------------------

END OF DOCUMENT