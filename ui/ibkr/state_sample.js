window.CSS_IBKR_SAMPLE_STATE = {
  timestamp: "2026-05-08T00:00:00+00:00",
  shadow_mode: true,
  session: {
    session_id: "CSS-SHADOW-SESSION",
    user_id: "demo_user",
    role: "TRADER",
    cycle_number: 42,
    engine_mode: "SAFE",
    live_or_paper: "paper",
    resolved_mode: "paper"
  },
  session_id: "CSS-SHADOW-SESSION",
  user_id: "demo_user",
  role: "TRADER",
  cycle_number: 42,
  engine_mode: "SAFE",
  live_or_paper: "paper",
  broker_mode: "paper",
  resolved_mode: "paper",
  broker_summary: {
    selected_broker: "COINBASE_SIM",
    broker_mode: "paper",
    connected: true,
    live_trading_enabled: false,
    last_heartbeat: "2026-05-08T00:00:00+00:00"
  },
  account_summary: {
    broker: "COINBASE_SIM",
    account_mode: "paper",
    currency: "USD",
    cash_balance: 10000.0,
    total_equity: 10250.0,
    buying_power: 5000.0,
    margin_used: 1000.0,
    available_margin: 4000.0
  },
  pnl_summary: {
    realized_pnl: 0.0,
    unrealized_pnl: 27.5,
    net_pnl: 27.5,
    winners: 2,
    losers: 0,
    win_rate: 100.0
  },
  risk_summary: {
    risk_state: "NORMAL",
    gate_status: "OPEN",
    total_exposure: 4362.5,
    exposure_utilization_pct: 42.56,
    current_drawdown_pct: 0.35,
    max_drawdown_pct: 2.0,
    daily_loss_limit: 500.0,
    position_limit: 10,
    exposure_limit: 25000.0,
    risk_limits_breached: []
  },
  governance_summary: {
    governance_enabled: true,
    session_locked: false,
    defensive_mode_active: false,
    unified_trade_gate_active: true,
    audit_enabled: true,
    last_governance_event: "Shadow UI governance state hydrated"
  },
  market_summary: {
    trend_state: "UPTREND",
    volatility_state: "NORMAL",
    liquidity_state: "HEALTHY",
    mean_reversion_state: "NEUTRAL",
    probability_state: "FAVORABLE",
    velocity_state: "RISING",
    vwap_state: "ABOVE_VWAP",
    vwap_distance: 0.0125,
    vwap_elasticity: 0.83,
    momentum_state: "POSITIVE",
    pressure_state: "BUY_PRESSURE",
    acceleration_state: "STABLE",
    regime_state: "RISK_ON",
    spread_state: "TIGHT",
    execution_cost_state: "ACCEPTABLE",
    signal_confluence_state: "CONFIRMED"
  },
  execution_summary: {
    execution_state: "READY",
    accepted_trade_count: 2,
    rejected_trade_count: 0,
    pending_trade_count: 0,
    total_execution_cost: 1.25,
    slippage_cost: 0.5,
    spread_cost: 0.45,
    fee_cost: 0.3,
    avg_slippage_bps: 1.2,
    avg_spread_bps: 0.8,
    execution_cost_state: "ACCEPTABLE",
    last_execution_event: "Shadow execution summary hydrated"
  },
  open_positions: {
    total: 2,
    by_asset: {
      CRYPTO: 1,
      FX: 1,
      FUTURES: 0,
      OPTIONS: 0
    }
  },
  positions: [
    {
      symbol: "BTC-USD",
      asset_class: "CRYPTO",
      side: "LONG",
      qty: 0.05,
      entry_price: 65000.0,
      mark_price: 65500.0,
      unrealized_pnl: 25.0,
      exposure: 3275.0
    },
    {
      symbol: "EUR_USD",
      asset_class: "FX",
      side: "SHORT",
      qty: 1000,
      entry_price: 1.09,
      mark_price: 1.0875,
      unrealized_pnl: 2.5,
      exposure: 1087.5
    }
  ],
  opportunities: [
    {
      symbol: "ETH-USD",
      asset_class: "CRYPTO",
      side: "WATCH",
      score: 82,
      signal: "VWAP support with confirmed pressure"
    },
    {
      symbol: "CL",
      asset_class: "FUTURES",
      side: "HOLD",
      score: 64,
      signal: "Cost state acceptable, momentum cooling"
    }
  ],
  alerts: [
    {
      level: "info",
      title: "Shadow mode active",
      detail: "UI is not authorized to route orders."
    },
    {
      level: "warning",
      title: "Live order control disabled",
      detail: "Enablement must come from CSS governance and execution gates."
    }
  ],
  equity_series: [10000, 10022, 10015, 10080, 10125, 10210, 10250],
  risk_bands: [
    { label: "Drawdown", value: 0.35, limit: 2.0 },
    { label: "Exposure", value: 42.56, limit: 100.0 },
    { label: "Positions", value: 2, limit: 10 }
  ]
};
