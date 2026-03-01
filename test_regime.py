import pandas as pd
from engine.regime.regime_classifier import classify_regime

df = pd.read_csv("sample_spy_1m_long.csv")

# reuse normalization + resample logic quickly
df["ts_utc"] = pd.to_datetime(df["ts_utc"])
df = df.set_index("ts_utc")
df5 = df.resample("5min").agg({
    "o": "first",
    "h": "max",
    "l": "min",
    "c": "last"
}).dropna()

df5.columns = ["open", "high", "low", "close"]

regime = classify_regime(df5)
print(regime.value_counts())