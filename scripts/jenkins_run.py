"""Trigger and follow the dedicated localhost Jenkins controller without logging secrets."""
import argparse
import base64
import http.cookiejar
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor

BASE = 'http://localhost:8080'


def main(host, build_number=None):
    password = Path('.local/jenkins/secrets/admin_password').read_text().strip()
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path, data=None, headers=None):
        req = Request(BASE + path, data=data, headers={'Authorization': 'Basic ' + auth, **(headers or {})})
        return opener.open(req, timeout=15)
    def get(path):
        with request(path) as response:
            return json.load(response)
    deadline = time.monotonic() + 240
    while True:
        try:
            get('/job/Devops-project/api/json')
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise SystemExit('Jenkins did not become ready; inspect the controller logs')
            time.sleep(3)
    if build_number is None:
        crumb = get('/crumbIssuer/api/json')
        with request('/job/Devops-project/buildWithParameters',
                     urlencode(dict(DEPLOY='true', DEPLOY_HOST=host, TARGET_PLATFORM='linux/amd64', SMALL_INSTANCE='true')).encode(),
                     {crumb['crumbRequestField']: crumb['crumb'], 'Content-Type': 'application/x-www-form-urlencoded'}) as response:
            queue_path = response.headers['Location'].replace(BASE, '').rstrip('/')
        print('Jenkins deployment queued.', flush=True)
        deadline = time.monotonic() + 180
        while True:
            item = get(queue_path + '/api/json')
            if item.get('executable'):
                build_number = item['executable']['number']
                break
            if item.get('cancelled') or time.monotonic() >= deadline:
                raise SystemExit('Jenkins build did not start')
            time.sleep(2)
    path = f'/job/Devops-project/{build_number}'
    print(f'Following {BASE}{path}/', flush=True)
    offset = 0
    deadline = time.monotonic() + 2100
    while True:
        info = get(path + '/api/json')
        with request(path + f'/logText/progressiveText?start={offset}') as response:
            chunk = re.sub(r'\x1b\[8m.*?\x1b\[0m', '', response.read().decode(errors='replace'))
            offset = int(response.headers.get('X-Text-Size', offset))
        # Jenkins credentials masking remains enabled; print stage changes and useful results.
        for line in chunk.splitlines():
            if any(word in line for word in ('[Pipeline] { (', 'PASS:', 'passed', 'Error', 'ERROR', 'FAIL', 'Finished:', 'Sending build context', 'Loaded image:')):
                print(line, flush=True)
        if not info.get('building'):
            result = {key: info.get(key) for key in ('number', 'result', 'url', 'duration')}
            result['commit'] = next((rev.get('lastBuiltRevision',{}).get('SHA1') for rev in info.get('actions',[]) if rev.get('lastBuiltRevision')), None)
            Path('reports').mkdir(exist_ok=True)
            Path('reports/jenkins-build.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result, indent=2), flush=True)
            if info.get('result') != 'SUCCESS':
                with request(path + '/consoleText') as response:
                    print('\n'.join(response.read().decode(errors='replace').splitlines()[-90:]))
                raise SystemExit('Jenkins deployment failed')
            return
        if time.monotonic() >= deadline:
            raise SystemExit('Timed out following Jenkins; the controller may still be running the build')
        time.sleep(8)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--host', required=True)
    p.add_argument('--build', type=int)
    a = p.parse_args()
    main(a.host, a.build)
