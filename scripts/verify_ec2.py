"""Read-only verification. Run over SSH from /opt/sentinel; output contains no credentials."""
import base64
import json
import math
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=10) as response:
        return json.load(response)


def verify():
    env = dict(line.split('=',1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#') and '=' in line)
    auth = base64.b64encode(('admin:' + env['GRAFANA_ADMIN_PASSWORD']).encode()).decode()
    status = fetch('http://localhost:8001/api/status')
    assert status['ready'] and not status['stale'] and status['source'] == 'node', 'Node collection must be ready and fresh'
    dashboard = fetch('http://localhost:3000/api/dashboards/uid/server-risk', {'Authorization':'Basic '+auth})['dashboard']
    checked = 0
    for panel in dashboard['panels']:
        for target in panel.get('targets', []):
            result = fetch('http://localhost:9090/api/v1/query?' + urlencode({'query': target['expr']}))
            assert result['status'] == 'success', target['expr']
            checked += 1
    metrics = {}
    for name in ('server_cpu_usage_percent','server_memory_usage_percent','server_disk_usage_percent'):
        query = fetch('http://localhost:9090/api/v1/query?' + urlencode({'query':name}))
        values = query['data']['result']
        assert len(values) == 1, 'Expected exactly one host'
        value = float(values[0]['value'][1])
        assert math.isfinite(value) and 0 <= value <= 100
        metrics[name] = value
    stat = os.statvfs('/')
    actual = 100 * (1 - stat.f_bavail/stat.f_blocks)
    assert abs(actual - metrics['server_disk_usage_percent']) < 1, 'Node disk usage must match the host root filesystem'
    rules = fetch('http://localhost:9090/api/v1/rules')['data']['groups']
    assert all(r['health'] == 'ok' for group in rules for r in group['rules'])
    return dict(verified_at_utc=datetime.now(timezone.utc).isoformat(),
                system=platform.machine(), source=status['source'],
                model_synthetic=status['model']['synthetic'],
                dashboard_title=dashboard['title'], dashboard_queries_checked=checked,
                metrics=metrics, actual_root_disk_pct=actual,
                deployment=json.loads(Path('deployment.json').read_text()),
                note='Live EC2 resource collection verified. The image contains a synthetic demo ML model; representative host calibration and real held-out ML validation remain separate tasks.')


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
