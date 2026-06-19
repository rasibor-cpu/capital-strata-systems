# Phase 126 Trade Outcome Analytics and Profitability Report

## Objective

CSS must become evidence-driven.

Future profitability improvements shall be based on measured trade outcomes rather than assumptions.

## Trade Data To Capture

For every closed trade record:

* Asset Class
* Symbol
* Entry Timestamp
* Exit Timestamp
* Holding Duration
* Entry Reason
* Exit Reason
* Entry Price
* Exit Price
* Quantity
* Realized PnL
* Maximum Favorable Excursion (MFE)
* Maximum Adverse Excursion (MAE)
* Win/Loss Classification

## Profitability Metrics

Calculate:

* Total Trades
* Winning Trades
* Losing Trades
* Win Rate
* Average Win
* Average Loss
* Profit Factor
* Net Realized PnL
* Largest Win
* Largest Loss
* Average Holding Time
* Max Drawdown

## Asset-Class Analytics

Produce separate performance statistics for:

* CRYPTO
* FX
* FUTURES
* OPTIONS

Metrics:

* Trade Count
* Win Rate
* Net PnL
* Average Trade PnL
* Profit Factor

## Entry Signal Analytics

Track profitability by:

* Entry Reason
* Signal Type
* Composite Score Bucket
* Probability Bucket

Determine:

* Highest performing signals
* Lowest performing signals

## Exit Analytics

Track profitability by:

* Profit Target Exit
* Time Exit
* Defensive Exit
* Forced Exit
* Drawdown Exit

Determine which exits preserve the most profit.

## Capital Allocation Analytics

Determine:

* Which asset classes deserve increased allocation
* Which asset classes should be reduced
* Which classes should be temporarily suspended

## Cost Reality Layer

Future implementation should support:

* Spread
* Slippage
* Fees
* Financing Cost
* Options Decay

Generate both:

Gross PnL

and

Net PnL

## Future Runtime Files

Planned:

analytics/trade_outcome_analyzer.py

analytics/profitability_report.py

tests/analytics/test_trade_outcome_analyzer.py

tests/analytics/test_profitability_report.py

## Acceptance Criteria

CSS shall be able to answer:

* What makes money?
* What loses money?
* Which asset class is strongest?
* Which signal is strongest?
* Which exit is strongest?
* What is true profitability after costs?

## Recommendation

No new trading strategies should be added until profitability analytics are available.

Measurement precedes optimization.
