import json
import time
from urllib.request import urlopen


def fetch(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def main():
    deadline = time.monotonic() + 180
    while True:
        try:
            assert fetch("http://localhost:8001/readyz")["ready"]
            assert fetch("http://localhost:3000/api/health")["database"] == "ok"
            rules = fetch("http://localhost:9090/api/v1/rules")["data"]["groups"]
            assert rules and all(rule.get("health") == "ok" for group in rules for rule in group["rules"])
            targets = fetch("http://localhost:9090/api/v1/targets")["data"]["activeTargets"]
            assert any(t["labels"]["job"] == "server" and t["health"] == "up" for t in targets)
            print("PASS: model ready, Grafana healthy, Prometheus scraping, rules healthy")
            return
        except (Exception, AssertionError) as error:
            if time.monotonic() >= deadline:
                raise SystemExit(f"Smoke test failed: {error}")
            time.sleep(3)


if __name__ == "__main__":
    main()
