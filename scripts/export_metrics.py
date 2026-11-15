"""Export aligned Prometheus samples in the shared training CSV contract."""
import argparse
import csv
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def export(base, seconds, output, host, scenario, label):
    end = int(time.time())
    start = end - seconds
    series = []
    expressions = ["server_cpu_usage_percent", "server_memory_usage_percent", "server_disk_usage_percent"]
    for expr in expressions:
        query = f'{expr}{{host={json.dumps(host)}}} and on(instance,job) server_data_fresh'
        url = base + "/api/v1/query_range?" + urlencode(dict(query=query, start=start, end=end, step=2))
        with urlopen(url, timeout=10) as response:
            results = json.load(response)["data"]["result"]
        if len(results) != 1:
            raise ValueError("Expected one host series; check --host and freshness")
        series.append({float(t): float(v) for t, v in results[0]["values"] if math.isfinite(float(v))})
    times = sorted(set.intersection(*(set(values) for values in series)))
    if not times:
        raise ValueError("No aligned samples")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp_utc", "host", "cpu_pct", "ram_pct", "disk_used_pct", "run_id", "scenario", "label"])
        for t in times:
            writer.writerow([datetime.fromtimestamp(t, timezone.utc).isoformat(), host,
                             *(values[t] for values in series), f"live-{start}", scenario, label])
    print(f"Exported {len(times)} aligned rows to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:9090")
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--output", default="data/live.csv")
    parser.add_argument("--host", default="demo-linux")
    parser.add_argument("--scenario", choices=["normal", "spike", "growth"], default="normal")
    parser.add_argument("--label", type=int, choices=[0, 1], default=0)
    args = parser.parse_args()
    export(args.url, args.seconds, args.output, args.host, args.scenario, args.label)
