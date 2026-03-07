from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ManagedPosition:
    asset: str
    entry_price: float
    size: float
    tp1: float
    tp2: float
    trailing_stop: float
    tp1_hit: bool = False
    tp2_hit: bool = False


class TradeManager:
    """
    Phase 2 Trade Management Engine

    Handles profit laddering, trailing stops,
    and position management.
    """

    def __init__(self):

        self.positions = {}

    def open_position(self, asset: str, entry_price: float, size: float):

        tp1 = entry_price * 1.02
        tp2 = entry_price * 1.05
        trailing = entry_price * 0.98

        pos = ManagedPosition(
            asset=asset,
            entry_price=entry_price,
            size=size,
            tp1=tp1,
            tp2=tp2,
            trailing_stop=trailing
        )

        self.positions[asset] = pos

        print(f"Opened position {asset} entry={entry_price}")

    def update_price(self, asset: str, price: float):

        if asset not in self.positions:
            return

        pos = self.positions[asset]

        # TP1
        if not pos.tp1_hit and price >= pos.tp1:

            pos.tp1_hit = True
            pos.size *= 0.75

            print(f"{asset} TP1 reached. Partial profit taken.")

        # TP2
        if not pos.tp2_hit and price >= pos.tp2:

            pos.tp2_hit = True
            pos.size *= 0.75

            print(f"{asset} TP2 reached. Additional profit taken.")

        # trailing stop update
        new_trailing = price * 0.98

        if new_trailing > pos.trailing_stop:
            pos.trailing_stop = new_trailing

        # stop exit
        if price <= pos.trailing_stop:

            print(f"{asset} Trailing stop hit. Closing position.")

            del self.positions[asset]


def demo():

    manager = TradeManager()

    manager.open_position("BTC-USD", 100, 1)

    price_series = [101, 102, 103, 106, 108, 107, 104]

    for price in price_series:

        print("Price:", price)

        manager.update_price("BTC-USD", price)


if __name__ == "__main__":

    demo()