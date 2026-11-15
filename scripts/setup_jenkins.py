"""Prepare ignored local controller secrets, keeping credentials out of Git."""
import argparse
import secrets
import shutil
from pathlib import Path


def setup(host, key, known_hosts):
    root = Path.cwd().resolve()
    directory = root / '.local' / 'jenkins'
    secret_dir = directory / 'secrets'
    home = directory / 'home'
    secret_dir.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    secret_dir.chmod(0o700)
    for name in ('admin_password', 'grafana_password'):
        path = secret_dir / name
        if not path.exists():
            path.write_text(secrets.token_urlsafe(24) + '\n')
        path.chmod(0o600)
    shutil.copyfile(known_hosts, secret_dir / 'known_hosts')
    (secret_dir / 'known_hosts').chmod(0o600)
    config = root / '.local' / 'jenkins.env'
    config.write_text(f'JENKINS_HOST_HOME={home}\nJENKINS_SECRETS_DIR={secret_dir}\nEC2_KEY_FILE={Path(key).expanduser().resolve()}\nPROJECT_EC2_HOST={host}\n')
    config.chmod(0o600)
    # This file will be securely streamed to the deployment host.
    (directory / 'ec2.env').write_text('GRAFANA_ADMIN_PASSWORD=' + (secret_dir / 'grafana_password').read_text().strip() + '\nHOST_ID=ec2-monitor\nMODEL_PATH=/app/artifacts/model.joblib\n')
    (directory / 'ec2.env').chmod(0o600)
    print(f'Local controller settings prepared: {config}')
    print(f'Admin password is stored only in {secret_dir / "admin_password"}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--host', required=True)
    p.add_argument('--key', required=True)
    p.add_argument('--known-hosts', required=True)
    a = p.parse_args()
    setup(a.host, a.key, a.known_hosts)
