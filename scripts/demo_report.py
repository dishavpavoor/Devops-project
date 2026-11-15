"""Run a bounded real disk demo, then measure Prometheus alert lead times."""
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = "http://localhost:9090"


def get(path):
    with urlopen(BASE + path, timeout=5) as response:
        return json.load(response)


def range_series(expression, start, end):
    data = get("/api/v1/query_range?" + urlencode(dict(query=expression, start=start, end=end, step=2)))
    if data["status"] != "success":
        raise RuntimeError(data)
    return data["data"]["result"]


def first(series, predicate):
    times = [float(t) for row in series for t, value in row["values"] if predicate(float(value))]
    return min(times) if times else None


def run():
    subprocess.run(["docker", "compose", "exec", "-T", "monitor", "python", "-c",
                    "import urllib.request; urllib.request.urlopen('http://localhost:8001/readyz')"], check=True)
    # Ensure the full forecast lookback is available before the first write.
    print("Collecting 32 seconds of baseline...", flush=True)
    time.sleep(32)
    start = int(time.time())
    active = get("/api/v1/query?" + urlencode({"query": 'ALERTS{alertstate="firing"}'}))
    preexisting = {r["metric"]["alertname"] for r in active["data"]["result"]}
    subprocess.run(["docker", "compose", "exec", "-T", "monitor", "python", "-m", "monitor.demo"], check=True)
    time.sleep(6)
    end = int(time.time())
    disk = range_series("server_disk_usage_percent", start, end)
    crossing = first(disk, lambda v: v >= 95)
    times = {}
    for name in ("DiskPredictedToFill", "DiskUsageHigh", "ResourceAnomaly"):
        firing = first(range_series(f'ALERTS{{alertname="{name}",alertstate="firing"}}', start, end), lambda v: v == 1)
        times[name] = dict(first_firing_unix=firing, already_firing_at_start=name in preexisting,
                           lead_seconds=crossing-firing if crossing and firing and name not in preexisting else None)
    result = dict(start_unix=start, end_unix=end, disk_95_crossing_unix=crossing, alerts=times,
                  timing_resolution_seconds=2, note="Observed scrape/evaluation times; not exact write times. Preexisting alerts do not receive a lead time. Default synthetic ML model requires host calibration.")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/live-demo.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if crossing is None or times["DiskPredictedToFill"]["lead_seconds"] is None or times["DiskPredictedToFill"]["lead_seconds"] <= 0:
        raise SystemExit("FAIL: no predictive warning measured before 95%")
    print("PASS: predictive warning observed before 95%.")


if __name__ == "__main__":
    run()
