class ProfitCaptureEngine:

    def evaluate_exit(self, unrealized_pnl: float, momentum: float, position_direction: str):

        if unrealized_pnl > 0.5:
            return "TAKE_PROFIT"

        if unrealized_pnl < -0.3:
            return "STOP_LOSS"

        if momentum < 0 and position_direction == "LONG":
            return "EXIT_MOMENTUM"

        return "HOLD"
