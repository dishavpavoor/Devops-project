#!/bin/sh
# Invoked by Jenkins with credential bindings; never echo secret values.
set -eu
: "${DEPLOY_HOST:?Set DEPLOY_HOST}"
: "${SSH_KEY:?Bind the SSH private-key credential}"
: "${SSH_USER:?Bind the deployment username}"
: "${KNOWN_HOSTS:?Bind the verified known-hosts file}"
: "${BUILD_NUMBER:?Set the image build number}"
case "$DEPLOY_HOST" in *[!a-zA-Z0-9.-]*) echo 'Invalid deployment hostname'; exit 1;; esac
case "$BUILD_NUMBER" in *[!0-9]*) echo 'Invalid build number'; exit 1;; esac

compose_args='-f compose.yaml -f compose.linux.yaml'
if [ "${SMALL_INSTANCE:-false}" = true ]; then
    compose_args="$compose_args -f compose.small.yaml"
fi

docker save "sentinel-monitor:$BUILD_NUMBER" | gzip -1 > image.tar.gz
python3.12 - <<'PY'
import json, os, subprocess
from pathlib import Path
Path('deployment.json').write_text(json.dumps({
    'commit': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'build': os.environ['BUILD_NUMBER'],
    'platform': os.getenv('TARGET_PLATFORM','linux/amd64'),
    'job_url': os.getenv('BUILD_URL'),
}, indent=2)+'\n')
PY
tar -czf source.tar.gz compose.yaml compose.linux.yaml compose.small.yaml prometheus grafana alertmanager scripts artifacts deployment.json
scp -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 \
    -o UserKnownHostsFile="$KNOWN_HOSTS" -o StrictHostKeyChecking=yes \
    image.tar.gz source.tar.gz "$SSH_USER@$DEPLOY_HOST:/opt/sentinel/"
ssh -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 \
    -o UserKnownHostsFile="$KNOWN_HOSTS" -o StrictHostKeyChecking=yes "$SSH_USER@$DEPLOY_HOST" \
    "cd /opt/sentinel && test -f .env && tar -xzf source.tar.gz && gzip -dc image.tar.gz | docker load && IMAGE_TAG=$BUILD_NUMBER docker compose $compose_args up -d --no-build && python3 -m scripts.smoke"
