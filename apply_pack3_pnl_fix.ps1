$path = "scripts\css_live_dashboard.py"
$content = Get-Content $path -Raw

$pattern = 'def close_position\(self, symbol: str, exit_price: float\) -> float:[\s\S]*?return pnl'
$replacement = @"
def close_position(self, symbol: str, exit_price: float) -> float:
    pos = self.positions.pop(symbol, None)
    if pos is None:
        return 0.0

    side = str(pos.side or "LONG").upper()
    direction = 1.0 if side != "SHORT" else -1.0

    gross_pnl = (float(exit_price) - float(pos.entry_price)) * float(pos.quantity) * direction

    # PACK 3 FIX — COST MODEL
    entry_cost = float(pos.entry_price) * float(pos.quantity) * 0.001
    exit_cost  = float(exit_price) * float(pos.quantity) * 0.001

    net_pnl = gross_pnl - entry_cost - exit_cost

    self.realized_pnl += net_pnl
    self.current_balance += net_pnl

    return net_pnl
"@

$newContent = [regex]::Replace($content, $pattern, $replacement)

Set-Content -Path $path -Value $newContent -Encoding UTF8

Write-Host "Pack 3 PnL Fix Applied Successfully."