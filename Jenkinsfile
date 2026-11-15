pipeline {
  agent { label 'docker' }
  options { timestamps(); disableConcurrentBuilds() }
  parameters {
    booleanParam(name: 'DEPLOY', defaultValue: false, description: 'Deploy to the prepared EC2 instance')
    string(name: 'DEPLOY_HOST', defaultValue: '', description: 'EC2 IP or DNS name')
  }
  stages {
    stage('Checkout') { steps { checkout scm } }
    stage('Train and test') {
      steps {
        sh '''python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ml.train
.venv/bin/python -m ml.evaluate
.venv/bin/python -m pytest -q --junitxml=reports/tests.xml
'''
      }
    }
    stage('Validate monitoring rules') {
      steps {
        withCredentials([string(credentialsId: 'sentinel-grafana-password', variable: 'GRAFANA_ADMIN_PASSWORD')]) {
          sh 'docker compose config --quiet && docker compose run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml && docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/test_rules.yml'
        }
      }
    }
    stage('Build') {
      steps { sh 'docker build -f monitor/Dockerfile -t sentinel-monitor:$BUILD_NUMBER .' }
    }
    stage('Deploy and smoke test') {
      when { expression { params.DEPLOY } }
      steps {
        withCredentials([
          sshUserPrivateKey(credentialsId: 'sentinel-ec2-ssh', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
          file(credentialsId: 'sentinel-known-hosts', variable: 'KNOWN_HOSTS')
        ]) {
          sh '''set -eu
case "$DEPLOY_HOST" in ''|*[!a-zA-Z0-9.-]*) echo 'Invalid deployment hostname'; exit 1;; esac
docker save sentinel-monitor:$BUILD_NUMBER | gzip > image.tar.gz
tar -czf source.tar.gz compose.yaml compose.linux.yaml prometheus grafana alertmanager scripts artifacts
scp -i "$SSH_KEY" -o UserKnownHostsFile="$KNOWN_HOSTS" -o StrictHostKeyChecking=yes image.tar.gz source.tar.gz "$SSH_USER@$DEPLOY_HOST:/opt/sentinel/"
ssh -i "$SSH_KEY" -o UserKnownHostsFile="$KNOWN_HOSTS" -o StrictHostKeyChecking=yes "$SSH_USER@$DEPLOY_HOST" "cd /opt/sentinel && tar -xzf source.tar.gz && gzip -dc image.tar.gz | docker load && IMAGE_TAG=$BUILD_NUMBER docker compose -f compose.yaml -f compose.linux.yaml up -d --no-build && python3 -m scripts.smoke"
'''
        }
      }
    }
  }
  post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/tests.xml'
      archiveArtifacts artifacts: 'reports/evaluation.*,artifacts/model.json', allowEmptyArchive: true
    }
  }
}
