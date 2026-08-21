from pathlib import Path

import pandas as pd


RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def list_raw_csv_files() -> list[Path]:
    return sorted(p for p in RAW_DATA_DIR.glob("*.csv"))


def load_raw_csv(filename: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DATA_DIR / filename)
