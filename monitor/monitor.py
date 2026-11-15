"""Linux metrics + artifact-based inference. HTTP API is read-only."""
import json
import logging
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import joblib
import psutil
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import Gauge, Counter, start_http_server
from ml.features import VERSION, INTERVAL, WINDOW, features

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HOST = os.getenv("HOST_ID", "demo-linux")
SOURCE = os.getenv("METRICS_SOURCE", "local")
DISK = os.getenv("MONITOR_DISK_PATH", "/demo-disk")
MODEL = os.getenv("MODEL_PATH", "/app/artifacts/model.joblib")
PROMETHEUS = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
app = FastAPI(title="Sentinel • Server Early Warning", version="1.0.0")
lock = threading.Lock()
history = deque(maxlen=900)
state = {"host": HOST, "source": SOURCE, "ready": False, "last_sample": None, "error": None}


def query(expression):
    with urlopen(PROMETHEUS + "/api/v1/query?" + urlencode({"query": expression}), timeout=3) as response:
        body = json.load(response)
    results = body.get("data", {}).get("result", [])
    if body.get("status") != "success" or len(results) != 1:
        raise ValueError(f"Expected exactly one node series: {expression}")
    value = float(results[0]["value"][1])
    # Prometheus instant queries can return old samples. Check exporter up separately.
    if not math.isfinite(value):
        raise ValueError("Node metric is not finite")
    return value


def sample():
    if SOURCE == "node":
        if query('up{job="node"}') != 1:
            raise ValueError("Node Exporter is down")
        return [query('100 * (1 - avg(rate(node_cpu_seconds_total{job="node",mode="idle"}[1m])))'),
                query('100 * (1 - node_memory_MemAvailable_bytes{job="node"} / node_memory_MemTotal_bytes{job="node"})'),
                query('100 * (1 - node_filesystem_avail_bytes{job="node",mountpoint="/",fstype!="rootfs"} / node_filesystem_size_bytes{job="node",mountpoint="/",fstype!="rootfs"})')]
    return [psutil.cpu_percent(), psutil.virtual_memory().percent, psutil.disk_usage(DISK).percent]


@app.get("/healthz")
def health():
    return {"status": "running"}


@app.get("/readyz")
def readiness():
    with lock:
        ok = state["ready"] and state["last_sample"] is not None and time.time() - state["last_sample"] < 10
    return JSONResponse({"ready": bool(ok)}, status_code=200 if ok else 503)


@app.get("/api/status")
def status():
    with lock:
        result = dict(state)
    result["stale"] = result["last_sample"] is None or time.time() - result["last_sample"] >= 10
    return result


@app.get("/api/history")
def samples():
    with lock:
        return list(history)


def collect(bundle):
    labels = {"host": HOST}
    gauges = [Gauge(name, description, ["host"]).labels(**labels) for name, description in [
        ("server_cpu_usage_percent", "CPU usage percent"),
        ("server_memory_usage_percent", "Memory usage percent"),
        ("server_disk_usage_percent", "Selected filesystem usage percent")]]
    score = Gauge("server_anomaly_score", "Negative decision function: above zero means anomalous", ["host"]).labels(**labels)
    ready = Gauge("server_model_ready", "Model loaded and complete fresh feature window", ["host"]).labels(**labels)
    last = Gauge("server_last_sample_timestamp_seconds", "Last successful metric collection", ["host"]).labels(**labels)
    errors = Counter("server_collection_errors_total", "Failed collection attempts", ["host"]).labels(**labels)
    window = deque(maxlen=WINDOW)
    psutil.cpu_percent()
    previous = None
    while True:
        tick = time.monotonic()
        try:
            values = sample()
            if any(not math.isfinite(v) or not 0 <= v <= 100 for v in values):
                raise ValueError("Metric outside percentage contract")
            now = time.time()
            if previous is not None and tick - previous > INTERVAL + .25:
                window.clear()
            previous = tick
            window.append(values)
            anomaly = float(-bundle["model"].decision_function([features(window)])[0]) if len(window) == WINDOW else None
            for gauge, value in zip(gauges, values):
                gauge.set(value)
            if anomaly is not None:
                score.set(anomaly)
            ready.set(int(anomaly is not None))
            last.set(now)
            row = dict(timestamp_utc=datetime.fromtimestamp(now, timezone.utc).isoformat(), host=HOST,
                       cpu_pct=values[0], ram_pct=values[1], disk_used_pct=values[2], anomaly_score=anomaly)
            with lock:
                history.append(row)
                state.update(row, ready=anomaly is not None, last_sample=now, error=None)
        except Exception as error:
            logging.exception("Collection failed")
            errors.inc()
            ready.set(0)
            window.clear()
            previous = None
            with lock:
                state.update(ready=False, error=str(error))
        time.sleep(max(0, INTERVAL - (time.monotonic() - tick)))


def main():
    if SOURCE not in ("local", "node"):
        raise ValueError("METRICS_SOURCE must be local or node")
    if SOURCE == "local" and not Path(DISK).is_mount():
        raise ValueError("Local demo requires a dedicated mounted filesystem")
    bundle = joblib.load(MODEL)
    metadata = bundle["metadata"]
    if (metadata["feature_version"], metadata["interval"], metadata["window"]) != (VERSION, INTERVAL, WINDOW):
        raise ValueError("Incompatible model feature contract")
    state["model"] = metadata
    start_http_server(8000)
    threading.Thread(target=collect, args=(bundle,), daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")


if __name__ == "__main__":
    main()
