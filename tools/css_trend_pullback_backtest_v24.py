"""
Capital Strata Systems (CSS)
BTC Trend Pullback Backtest v24

Enhancements vs v23
1) Profit expansion (TP1 = 2R)
2) Wider trailing stop (3.5 ATR)
3) Slightly stronger trend filter
"""

from __future__ import annotations
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import requests

COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)

CFG = {
    "test_days": 180,
    "granularity": 900,
    "ema_fast": 20,
    "ema_slow": 50,
    "slope_lookback": 8,
    "min_slope_pct": 0.0013,
    "atr_window": 20,
    "atr_stop_mult": 2.0,
    "trail_atr_mult": 3.5,
    "min_atr_pct": 0.004,
    "cooldown": 10,
    "position_size": 0.05,
    "fee_rate": 0.0006,
    "tp1_r": 2.0,
    "tp1_frac": 0.5
}

@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def fetch(product,start,end,gran):
    url=f"{COINBASE}/products/{product}/candles"
    candles=[]
    step=gran*200
    cursor=start

    while cursor<end:
        chunk=min(cursor+timedelta(seconds=step),end)
        params={"start":_iso(cursor),"end":_iso(chunk),"granularity":gran}
        r=requests.get(url,params=params)

        if r.status_code!=200:
            raise RuntimeError(r.text)

        for row in r.json():
            ts,low,high,open_,close,vol=row
            candles.append(Candle(int(ts),float(low),float(high),float(open_),float(close),float(vol)))

        cursor=chunk
        time.sleep(0.12)

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
    if len(candles)<2:
        return None
    trs=[]
    prev=candles[0].close
    for c in candles[1:]:
        tr=max(c.high-c.low,abs(c.high-prev),abs(c.low-prev))
        trs.append(tr)
        prev=c.close
    return statistics.mean(trs)


def backtest():

    capital=1000
    cash=capital
    position=None
    cooldown=0
    trades=[]

    end=datetime.now(timezone.utc)
    start=end-timedelta(days=CFG["test_days"])

    candles=fetch("BTC-USD",start,end,CFG["granularity"])

    closes=[]
    warm=max(CFG["ema_slow"],CFG["atr_window"])+CFG["slope_lookback"]+5

    for i,c in enumerate(candles):

        closes.append(c.close)
        price=c.close

        if i<warm:
            continue

        if cooldown>0:
            cooldown-=1

        ema20=ema(closes[-CFG["ema_fast"]:],CFG["ema_fast"])
        ema50=ema(closes[-CFG["ema_slow"]:],CFG["ema_slow"])

        ema50_prev=ema(
            closes[-CFG["ema_slow"]-CFG["slope_lookback"]:-CFG["slope_lookback"]],
            CFG["ema_slow"]
        )

        if None in (ema20,ema50,ema50_prev):
            continue

        slope=(ema50-ema50_prev)/price
        if slope<CFG["min_slope_pct"]:
            continue

        atr_val=atr(candles[i-CFG["atr_window"]:i+1])
        if atr_val is None:
            continue

        if atr_val/price<CFG["min_atr_pct"]:
            continue

        uptrend=price>ema50

        if position is None and cooldown==0:

            if uptrend and price<=ema20:
                pullback=True
            else:
                pullback=False

            if pullback and price>ema20:

                size_usd=cash*CFG["position_size"]
                fee=size_usd*CFG["fee_rate"]

                cash-=size_usd+fee
                size_btc=size_usd/price

                stop=price-(CFG["atr_stop_mult"]*atr_val)
                r=price-stop

                position={
                    "entry":price,
                    "size":size_btc,
                    "stop":stop,
                    "peak":price,
                    "r":r,
                    "tp1_done":False
                }

        if position:

            if price>position["peak"]:
                position["peak"]=price

            trail=position["peak"]-(CFG["trail_atr_mult"]*atr_val)
            if trail>position["stop"]:
                position["stop"]=trail

            tp1=position["entry"]+(CFG["tp1_r"]*position["r"])

            if (not position["tp1_done"]) and c.high>=tp1:

                sell=position["size"]*CFG["tp1_frac"]
                val=sell*tp1
                fee=val*CFG["fee_rate"]

                pnl=(tp1-position["entry"])*sell-fee
                trades.append(pnl)

                cash+=val-fee
                position["size"]-=sell
                position["tp1_done"]=True

            if c.low<=position["stop"]:

                exitp=position["stop"]
                sell=position["size"]
                val=sell*exitp
                fee=val*CFG["fee_rate"]

                pnl=(exitp-position["entry"])*sell-fee
                trades.append(pnl)

                cash+=val-fee
                position=None
                cooldown=CFG["cooldown"]

    equity=cash

    if position:
        equity+=position["size"]*candles[-1].close

    wins=sum(1 for t in trades if t>0)
    losses=sum(1 for t in trades if t<=0)

    res={
        "strategy":"trend_pullback_v24",
        "trades":len(trades),
        "wins":wins,
        "losses":losses,
        "win_rate":round((wins/len(trades))*100,2) if trades else 0,
        "final_equity":round(equity,2),
        "pnl":round(equity-capital,2)
    }

    return res


def main():

    res=backtest()

    print("\nCSS TREND PULLBACK BACKTEST v24\n")
    print(res)

    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")

    out=OUT/f"trend_pullback_backtest_v24_{stamp}.json"

    out.write_text(json.dumps(res,indent=2))

    print("\nSaved:",out)


if __name__=="__main__":
    main()