"""Deterministic synthetic fixtures, never represented as real host data."""
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ml.features import COLUMNS, INTERVAL


def generate(directory="data"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for split, seed, scenarios in [("train", 42, ["normal"] * 4),
                                    ("test", 2026, ["normal", "spike", "growth", "normal"])]:
        rng = random.Random(seed)
        with (directory / f"{split}.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["timestamp_utc", "host", *COLUMNS, "run_id", "scenario", "label"])
            for run, scenario in enumerate(scenarios):
                for i in range(240):
                    cpu = max(0, min(100, rng.gauss(25, 7)))
                    ram = max(0, min(100, rng.gauss(45, 3)))
                    disk = rng.uniform(0, .15)
                    label = 0
                    if scenario == "spike" and 100 <= i < 110:
                        cpu, ram, label = 98, 85, 1
                    if scenario == "growth" and i >= 80:
                        disk, label = min(98, (i - 80) * .7), 1
                    time = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=run + (10 if split == "test" else 0), seconds=i * INTERVAL)
                    writer.writerow([time.isoformat(), "synthetic-demo", round(cpu, 4), round(ram, 4),
                                     round(disk, 4), f"{split}-{run}", scenario, label])


if __name__ == "__main__":
    generate()
