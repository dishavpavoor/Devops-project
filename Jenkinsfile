pipeline {
  agent { label 'docker' }
  options { timestamps(); disableConcurrentBuilds(); skipDefaultCheckout(true); timeout(time: 30, unit: 'MINUTES') }
  parameters {
    booleanParam(name: 'DEPLOY', defaultValue: false, description: 'Deploy to the prepared EC2 instance')
    string(name: 'DEPLOY_HOST', defaultValue: '', description: 'EC2 IP or DNS name')
    choice(name: 'TARGET_PLATFORM', choices: ['linux/amd64', 'linux/arm64'], description: 'Match the deployment host architecture')
    booleanParam(name: 'SMALL_INSTANCE', defaultValue: true, description: 'Bound memory and storage for a classroom t3.micro')
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
          sh 'docker compose config --quiet && docker compose run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml && docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/test_rules.yml && docker compose run --rm --no-deps --entrypoint promtool prometheus check rules /etc/prometheus/alerts.host.yml'
        }
      }
    }
    stage('Build') {
      steps { sh 'docker build --platform="$TARGET_PLATFORM" -f monitor/Dockerfile -t sentinel-monitor:$BUILD_NUMBER .' }
    }
    stage('Deploy and smoke test') {
      when { expression { params.DEPLOY } }
      steps {
        withCredentials([
          sshUserPrivateKey(credentialsId: 'sentinel-ec2-ssh', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
          file(credentialsId: 'sentinel-known-hosts', variable: 'KNOWN_HOSTS')
        ]) {
          sh 'sh scripts/deploy.sh'
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
