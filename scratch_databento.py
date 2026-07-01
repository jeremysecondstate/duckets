from pathlib import Path
import pandas as pd

root = Path(r"I:\My Drive\PRC\OHLCV")

files = sorted(root.rglob("*.parquet"))
print(f"Found {len(files)} parquet files")

for path in files[:50]:
    print(path)

if files:
    latest = files[-1]
    print("\nReading:", latest)

    df = pd.read_parquet(latest)
    print(df.shape)
    print(df.dtypes)
    print(df.head())
    print(df.tail())