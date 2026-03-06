"""
Capital Strata Systems
Execution Realism Backtest v29

Adds realistic trading frictions:
- spread
- slippage
- taker fees
- volatility widening

Uses the same Trend Pullback engine as v25
"""

from __future__ import annotations
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import requests

COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRODUCTS = ["BTC-USD","ETH-USD","SOL-USD"]

CFG = {

"test_days":180,
"granularity":900,

"ema_fast":20,
"ema_slow":50,
"slope_lookback":8,
"min_slope_pct":0.0013,

"atr_window":20,
"atr_stop_mult":2.0,
"trail_atr_mult":3.5,
"min_atr_pct":0.004,

"cooldown":10,
"position_size":0.05,

"taker_fee":0.006,
"spread":0.0005,
"slippage":0.0007,

"tp1_r":2.0,
"tp1_frac":0.5
}

@dataclass
class Candle:
    ts:int
    low:float
    high:float
    open:float
    close:float
    volume:float


def iso(t):
    return t.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def fetch(product,start,end,gran):

    url=f"{COINBASE}/products/{product}/candles"
    candles=[]

    step=gran*200
    cursor=start

    while cursor<end:

        chunk=min(cursor+timedelta(seconds=step),end)

        r=requests.get(url,params={
            "start":iso(cursor),
            "end":iso(chunk),
            "granularity":gran
        })

        for row in r.json():
            ts,low,high,open_,close,vol=row
            candles.append(Candle(ts,low,high,open_,close,vol))

        cursor=chunk
        time.sleep(0.1)

    uniq={c.ts:c for c in candles}

    return sorted(uniq.values(),key=lambda x:x.ts)


def ema(values,period):

    if len(values)<period:
        return None

    k=2/(period+1)

    e=values[0]

    for v in values:
        e=v*k+e*(1-k)

    return e


def atr(candles):

    trs=[]
    prev=candles[0].close

    for c in candles[1:]:

        tr=max(
            c.high-c.low,
            abs(c.high-prev),
            abs(c.low-prev)
        )

        trs.append(tr)
        prev=c.close

    return statistics.mean(trs)


def execution_price(price,is_buy=True):

    spread=CFG["spread"]
    slip=CFG["slippage"]*random.random()

    if is_buy:
        return price*(1+spread+slip)

    else:
        return price*(1-spread-slip)


def run(product):

    capital=1000
    cash=capital

    position=None
    cooldown=0
    in_pullback=False

    trades=[]

    end=datetime.now(timezone.utc)
    start=end-timedelta(days=CFG["test_days"])

    candles=fetch(product,start,end,CFG["granularity"])

    closes=[]

    warm=60

    for i,c in enumerate(candles):

        closes.append(c.close)
        price=c.close

        if i<warm:
            continue

        if cooldown>0:
            cooldown-=1

        ema20=ema(closes[-20:],20)
        ema50=ema(closes[-50:],50)

        ema50_prev=ema(
            closes[-50-CFG["slope_lookback"]:-CFG["slope_lookback"]],
            50
        )

        if not ema20 or not ema50 or not ema50_prev:
            continue

        slope=(ema50-ema50_prev)/price

        if slope<CFG["min_slope_pct"]:
            continue

        atr_val=atr(candles[i-20:i+1])

        if atr_val/price<CFG["min_atr_pct"]:
            continue

        uptrend=price>ema50

        if uptrend and price<=ema20:
            in_pullback=True

        if position is None and cooldown==0 and in_pullback and price>ema20:

            entry=execution_price(price,True)

            size=(cash*CFG["position_size"])/entry

            fee=size*entry*CFG["taker_fee"]

            cash-=size*entry+fee

            stop=entry-(CFG["atr_stop_mult"]*atr_val)

            position={
                "entry":entry,
                "size":size,
                "stop":stop,
                "peak":entry
            }

            in_pullback=False

        if position:

            if price>position["peak"]:
                position["peak"]=price

            trail=position["peak"]-(CFG["trail_atr_mult"]*atr_val)

            if trail>position["stop"]:
                position["stop"]=trail

            if c.low<=position["stop"]:

                exitp=execution_price(position["stop"],False)

                size=position["size"]

                fee=size*exitp*CFG["taker_fee"]

                pnl=(exitp-position["entry"])*size-fee

                cash+=size*exitp-fee

                trades.append(pnl)

                position=None
                cooldown=CFG["cooldown"]

    equity=cash

    wins=sum(1 for t in trades if t>0)

    return {

        "product":product,
        "trades":len(trades),
        "wins":wins,
        "losses":len(trades)-wins,
        "final_equity":round(equity,2),
        "pnl":round(equity-capital,2)
    }


def main():

    print("\nCSS EXECUTION REALISM TEST v29\n")

    portfolio=0

    for p in PRODUCTS:

        r=run(p)

        portfolio+=r["pnl"]

        print(r)

    print("\nPortfolio PnL:",round(portfolio,2))


if __name__=="__main__":
    main()