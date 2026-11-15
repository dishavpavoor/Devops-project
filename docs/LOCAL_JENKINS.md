# Local Jenkins → existing EC2 deployment

This configuration runs Jenkins on your development machine and deploys monitoring to an existing small EC2 instance. It requires no AWS access key in Jenkins and does not create or resize cloud resources.

The tested target is x86 Ubuntu 26.04 on t3.micro. Ansible installs Docker and Compose; Python inference runs inside the Python 3.12 image, so it does not depend on the host Python version. A 512 MiB swap file helps short memory peaks. `compose.small.yaml` bounds service memory and limits Prometheus retention to 24 hours / 256 MB. This is a classroom demo configuration, not a production capacity recommendation.

## Prepare the local controller

Install Docker Desktop and verify SSH access to the existing instance. The initial SSH connection must establish the expected host key; the deployment pipeline then enforces that recorded key.

```sh
python3 -m scripts.setup_jenkins \
  --host EC2_PUBLIC_IP \
  --key /absolute/path/to/project-key.pem \
  --known-hosts /absolute/path/to/verified-known-hosts

docker compose --env-file .local/jenkins.env -f compose.jenkins.yaml up --build -d
```

The generated `.local/` directory is ignored by Git and Docker builds. It contains the Jenkins administrator password and controller state. The `.pem` key is mounted read-only, and its contents are stored in Jenkins' credential store. No secret values are written into source files or console logs. Back up controller state privately if needed.

Open `http://localhost:8080`, username `admin`; the generated password is in `.local/jenkins/secrets/admin_password`. The first startup seeds the `Devops-project` job and its deployment credentials. It does not reset an initialized controller on restart.

This trusted local demo controller runs as container root and has access to the Docker Desktop socket so it can build images. Docker access can control the local Docker environment. Keep the interface bound to localhost, allow only trusted project code to run, and use dedicated build agents for a shared installation.

Matching host/container Jenkins-home paths allow Compose's workspace bind mounts to work with the Docker Desktop daemon. The image includes Python 3.12, Docker CLI/Compose and the required Pipeline/Git/credentials/JUnit plugins.

## Prepare and deploy the existing instance

Run the host playbook with your own ignored inventory. Its small-instance swap tasks run only on hosts with less than 1.5 GiB RAM:

```sh
ansible-playbook -i your-local-inventory.ini deploy/ansible/setup.yml
```

Securely copy the generated `.local/jenkins/ec2.env` to `/opt/sentinel/.env`, owned by the deployment user with mode 600. The pipeline preserves that file. It selects the reproducible synthetic model initially; retrain on representative EC2 normal data before interpreting live ML warnings.

In Jenkins, select **Devops-project → Build with Parameters**:

- `DEPLOY=true`
- `DEPLOY_HOST` = the existing EC2 address
- `TARGET_PLATFORM=linux/amd64` for x86 EC2, even when Jenkins runs on an Apple Silicon Mac
- `SMALL_INSTANCE=true` for this t3.micro

Alternatively, the local helper follows the same authenticated job:

```sh
python3 -m scripts.jenkins_run --host EC2_PUBLIC_IP
```

The pipeline checks out Git, trains/evaluates the model, runs tests, validates demo/host Prometheus rules, builds the correct architecture image, transfers it over verified SSH, starts the small Linux stack, and smoke-tests it. `reports/jenkins-build.json` records the observed build result. `deployment.json` on the server records the deployed Git revision and image build number.

## View EC2 services

If the local demo already uses port 3000, forward the EC2 dashboard to port 3001:

```sh
ssh -i /absolute/path/to/project-key.pem \
  -L 3001:localhost:3000 -L 9091:localhost:9090 \
  -L 9094:localhost:9093 -L 8002:localhost:8001 ubuntu@EC2_PUBLIC_IP
```

Open Grafana at `http://localhost:3001/d/server-risk`; username `admin`, password in `.local/jenkins/secrets/grafana_password`. The EC2 API is at `http://localhost:8002/api/status`. Jenkins remains at local port 8080. HTTP/HTTPS and dashboard ports do not need public inbound rules.

Stopping local Jenkins does not stop the deployed EC2 stack. Stopping the EC2 instance interrupts monitoring and may change its public IP; update your tunnel and Jenkins host parameter if that happens. No root-filesystem disk-fill experiment is permitted in Linux mode.
