@echo off
setlocal
cd /d C:\Users\rasib\source\REA-capital-trading-engine

python run_fx_pairs_replay_v4_fxrules_counters.py --csv "C:\Users\rasib\source\REA-capital-trading-engine\data_fx\EUR_USD_1m.csv" --symbol EURUSD --adapter auto

endlocal