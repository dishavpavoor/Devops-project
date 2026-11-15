"""One versioned feature contract shared by training and online inference."""
import csv
import math
from datetime import datetime
from collections import deque
import numpy as np

COLUMNS = ("cpu_pct", "ram_pct", "disk_used_pct")
INTERVAL = 2
WINDOW = 10
VERSION = 1
NAMES = [f"{col}_{stat}" for col in COLUMNS for stat in ("mean", "std", "slope_per_second")]


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp_utc must have UTC timezone")
    return dt.timestamp()


def features(samples):
    values = np.asarray(samples, dtype=float)
    if values.shape != (WINDOW, 3) or not np.isfinite(values).all():
        raise ValueError(f"Expected {WINDOW} finite three-metric samples")
    if (values < 0).any() or (values > 100).any():
        raise ValueError("Percentages must be in [0,100]")
    seconds = np.arange(WINDOW) * INTERVAL
    return np.array([v for series in values.T for v in
                     (series.mean(), series.std(), np.polyfit(seconds, series, 1)[0])])


def load_rows(path):
    with open(path, newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("CSV is empty")
    for row in rows:
        timestamp(row["timestamp_utc"])
        if not row["host"].strip():
            raise ValueError("host is required")
        for col in COLUMNS:
            row[col] = float(row[col])
            if not math.isfinite(row[col]) or not 0 <= row[col] <= 100:
                raise ValueError(f"Invalid {col}")
    return rows


def windows(rows):
    window = deque(maxlen=WINDOW)
    previous = None
    for row in rows:
        now = timestamp(row["timestamp_utc"])
        key = (row["host"], row.get("run_id", "default"))
        if previous:
            old_key, old_time = previous
            if key != old_key:
                window.clear()
            elif now <= old_time:
                raise ValueError("Timestamps must increase within a run")
            elif abs(now - old_time - INTERVAL) > 0.25:
                window.clear()  # Never join across missing samples.
        window.append([row[col] for col in COLUMNS])
        previous = (key, now)
        if len(window) == WINDOW:
            yield row, features(window)
