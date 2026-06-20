import dashboard.mobile.mobile_app as mobile_app
from pathlib import Path
tmp = Path('c:/temp/css3')
tmp.mkdir(parents=True, exist_ok=True)
mobile_app.MOBILE_EVENTS_FILE = tmp / 'events.jsonl'
mobile_app.MOBILE_CONTROL_FILE = tmp / 'controls.json'
mobile_app.save_mobile_controls({'mobile_trading_mode': 'MOBILE_PAPER_TRADING', 'engine_mode': 'SAFE', 'live_order_kill_switch': True})

def mock_eval(*args, **kwargs):
    return {'decision': {'final': 'ALLOW'}, 'reason': 'approved'}

from engine.execution.execution_gate import ExecutionGate
ExecutionGate.evaluate_trade = mock_eval

res = mobile_app.execute_mobile_trade_ticket({'user_id': '00017', 'display_name': 'CSS Trader', 'role': 'TRADER'}, {'broker': 'CSS_PAPER', 'asset_class': 'CRYPTO', 'symbol': 'ETH-USD', 'side': 'BUY', 'amount': '1000.00', 'qty': '10'})
print(res)
