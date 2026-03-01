from engine.decision_builder import GateInputs, build_trade_execution_decision
from engine.adapters.super_execution_gate_adapter import SuperExecutionGateAdapter

inputs = GateInputs(
    instrument="EUR_USD",
    snapshot={"price": 1.10},
    risk={
        "instrument": "EUR_USD",
        "side": "buy",
        "notional": 1000,
        "stop_distance_pct": 0.01,
        "equity": 100000,
        "equity_peak": 100000,
        "policy": "core",
    },
)

gates = {
    "super_execution_gate": lambda x: SuperExecutionGateAdapter().evaluate(
        state={
            "instrument": "EUR_USD",
            "side": "buy",
            "notional": 1000,
            "stop_distance_pct": 0.01,
            "equity": 100000,
            "equity_peak": 100000,
            "policy": "core",
        }
    )
}

decision = build_trade_execution_decision(
    engine_run_id="test_run",
    mode="paper",
    inputs=inputs,
    gates=gates,
)

print(decision)
print("\n--- Gate results ---")
for k, v in decision.gate_results.items():
    print(k, "=>", v.decision, "|", v.reason)
print("\nPrimary:", decision.primary_reason)

