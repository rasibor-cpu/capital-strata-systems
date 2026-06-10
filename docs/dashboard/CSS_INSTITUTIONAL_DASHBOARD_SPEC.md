CSS Institutional Dashboard Specification

Project: Capital Strata Systems (CSS)
Branch: phase71-church-governance-pack
Document Version: 1.0
Status: Draft for Governance Approval

---

1. Purpose

This document defines the target institutional dashboard architecture for Capital Strata Systems (CSS).

The dashboard shall provide a single authoritative operational view of platform status, capital deployment, portfolio performance, governance status, and trading activity across all supported asset classes.

The dashboard shall remain broker-agnostic and asset-class extensible.

---

2. Design Principles

The CSS Dashboard shall be:

- Governance First
- Capital Preservation Focused
- Operationally Transparent
- Audit Friendly
- Multi-Asset
- Broker Agnostic
- Mobile Compatible
- Institution Ready

The dashboard shall never become the authoritative source of truth.

Authoritative state remains within the runtime and governance layers.

The dashboard shall consume and display authoritative state.

---

3. Supported Asset Classes

The dashboard shall support:

- Foreign Exchange (FX)
- Cryptocurrency
- Futures
- Options
- Equities
- ETFs
- Fixed Income (Future)
- Alternative Assets (Future)

New asset classes shall be capable of integration without redesign of dashboard architecture.

---

4. Executive Summary Panel

The Executive Summary Panel shall display:

- Total Portfolio Value
- Available Capital
- Capital Deployed
- Open Positions
- Closed Positions
- Daily P&L
- Weekly P&L
- Monthly P&L
- Lifetime P&L
- Current Mode
- Active Broker
- Session Status

This panel shall remain visible at all times.

---

5. Asset Class Performance Panel

Performance shall be displayed by asset class.

FX

- Open Positions
- Closed Positions
- Realized P&L
- Unrealized P&L
- Win Rate

---

Crypto

- Open Positions
- Closed Positions
- Realized P&L
- Unrealized P&L
- Win Rate

---

Futures

- Open Positions
- Closed Positions
- Realized P&L
- Unrealized P&L
- Win Rate

---

Options

- Open Positions
- Closed Positions
- Realized P&L
- Unrealized P&L
- Win Rate

---

Equities

- Open Positions
- Closed Positions
- Realized P&L
- Unrealized P&L
- Win Rate

---

6. Portfolio Allocation Panel

Display:

- Allocation by Asset Class
- Allocation by Broker
- Allocation by Strategy
- Allocation by Risk Tier

Visual representation should support:

- Pie Chart
- Allocation Table
- Percentage View

---

7. Exposure Panel

Display:

- Gross Exposure
- Net Exposure
- Long Exposure
- Short Exposure
- Asset-Class Exposure
- Broker Exposure

Purpose:

Provide immediate visibility of concentration risk.

---

8. Trade Activity Panel

Display:

- Recent Trades
- Open Trades
- Closed Trades
- Pending Orders
- Rejected Orders

Each trade record should display:

- Asset
- Direction
- Entry
- Exit
- Quantity
- P&L
- Status

---

9. Governance Panel

Display:

- Current Trading Mode
- Governance Status
- Active Restrictions
- Kill Switch Status
- Capital Governor Status
- Session Expiry Status
- Policy Version

This panel shall be considered mandatory.

---

10. Risk Panel

Display:

- Current Drawdown
- Maximum Drawdown
- Daily Risk Utilization
- Portfolio Risk Utilization
- Concentration Risk
- Open Risk Exposure

Purpose:

Provide real-time visibility of portfolio risk.

---

11. Runtime Events Panel

Display:

- Runtime Events
- Governance Events
- Execution Events
- Broker Events
- Security Events

Filtering shall be supported.

---

12. Replay Panel

Display:

- Historical Events
- Trade Replay
- Runtime Replay
- Governance Replay

Purpose:

Provide operational auditability.

---

13. Performance Analytics Panel

Display:

- Win Rate
- Loss Rate
- Profit Factor
- Average Winner
- Average Loser
- Sharpe Ratio
- Sortino Ratio
- Expectancy
- Capital Efficiency

These metrics shall be calculated from authoritative accounting records.

---

14. Mobile Dashboard Requirements

Dashboard shall remain usable on:

- Samsung S24 Ultra
- Mobile browsers
- Tablets

Priority:

- Single-screen visibility
- Reduced scrolling
- Touch-friendly controls
- Readable metrics

---

15. Future Expansion Requirements

The dashboard architecture shall support future integration of:

- Additional Brokers
- Additional Asset Classes
- Additional Intelligence Engines
- Additional Governance Modules
- SaaS Multi-Tenant Reporting

without redesign of core dashboard structure.

---

16. Success Definition

The CSS Dashboard is successful when:

- All supported asset classes are visible
- Portfolio state is immediately understandable
- Governance state is immediately understandable
- Risk state is immediately understandable
- Capital state is immediately understandable
- Dashboard remains synchronized with authoritative runtime state

and

The platform can be operated from the dashboard without loss of governance visibility.

---

End of Document
