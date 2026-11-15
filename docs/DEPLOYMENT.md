# EC2, Terraform, Ansible and Jenkins

For the complete GitHub-to-Jenkins-to-EC2 sequence, start with [the integration guide](GITHUB_AWS_JENKINS.md).

The existing EC2 instance has been configured using the host Ansible playbook and deployed through local Jenkins; see [the current setup](LOCAL_JENKINS.md). The Terraform and separate Jenkins-on-Ubuntu instructions below describe optional alternative setups. Terraform has not been applied. AWS resources incur costs. Keep the EC2 instance running only as long as needed for your assessment.

## 1. Provision a host

Prerequisites: Terraform >=1.7, AWS credentials configured through the normal AWS credential chain, an existing EC2 key pair, a VPC and public subnet with internet access, and your public IPv4 address.

```sh
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit the values; admin_cidr should normally be your public IP /32.
terraform init
terraform plan
terraform apply
```

Only SSH is allowed inbound. Dashboard and API ports remain bound to the host's localhost. Use the `ssh_tunnel` Terraform output to access them. Do not expose Docker or unauthenticated Prometheus directly to the internet.

## 2. Prepare Ubuntu

From the repository root:

```sh
cp deploy/ansible/inventory.ini.example deploy/ansible/inventory.ini
# Replace the hostname and private-key path.
ansible-playbook -i deploy/ansible/inventory.ini deploy/ansible/setup.yml
```

Reconnect after Ansible runs so the Docker group change takes effect. Membership in the Docker group grants administrative access to the machine. Install only on a host intended for this project.

## 3. Deploy manually

Copy the repository to `/opt/sentinel` using your preferred Git checkout or scp process. Do not upload your private key, `.git` directory, `.venv` environments or local `.env` file.

On the host:

```sh
cd /opt/sentinel
cp .env.example .env
# Edit password and HOST_ID; use a real host identifier.
docker compose -f compose.yaml -f compose.linux.yaml config --quiet
docker compose -f compose.yaml -f compose.linux.yaml up --build -d
python3 -m scripts.smoke
```

Node Exporter measures the Linux root filesystem. The monitor queries one Node Exporter target through Prometheus. The first CPU rate needs enough scrape history, so allow up to a minute for readiness. The demo fill command is disabled in Linux mode. Never run a disk-filling experiment on the root filesystem.

Use an SSH tunnel from your laptop:

```sh
ssh -i ~/.ssh/your-key.pem -L 3000:localhost:3000 -L 9090:localhost:9090 -L 9093:localhost:9093 -L 8001:localhost:8001 ubuntu@EC2_IP
```

Then open the same localhost dashboard and API links as the local demo.

## 4. Calibrate the host model

The image initially has a synthetic demo model. After collecting representative normal host activity, export at least 10 minutes and train a model using the instructions in the main README. On EC2 you can run training with the installed monitor image and a writable working-directory bind mount, or install Python 3.12 and the requirements into a virtual environment.

Example container training (run from the host repo directory after exporting the CSV):

```sh
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" -w /workspace monitor \
  python -m ml.train --csv data/live-normal.csv --output artifacts/host.joblib
```

Set `MODEL_PATH=/models/host.joblib` in the host `.env` and recreate the monitor using both Compose files. Train/test files require distinct run IDs. Use multiple normal workload periods and held-out test runs; one idle recording is only an initial calibration.

## 5. Jenkins

The Jenkins agent labeled `docker` needs Docker, Compose, Python 3.12, pip/venv, ssh/scp, tar, gzip and access to this Git repository. Add these Jenkins credentials:

| Credential ID | Type | Purpose |
|---|---|---|
| `sentinel-grafana-password` | Secret text | Compose validation stages |
| `sentinel-ec2-ssh` | SSH username/private key | Deploy to the prepared EC2 host |
| `sentinel-known-hosts` | Secret file | Verified SSH host key entry for that exact host |

Create `/opt/sentinel/.env` on the host before deploying. It is never overwritten by the pipeline. The host password must match that file; the Jenkins validation password does not change the deployed password.

Create a Pipeline job from SCM using `Jenkinsfile`. The default run trains, evaluates, tests, validates rules and builds. Enable the `DEPLOY` parameter and set `DEPLOY_HOST` to deploy the tested image to the host. The pipeline tags the image by build number, ships the image and configurations over verified SSH, then runs a smoke test remotely. No registry is required.

A normal pipeline run validates the demo rules; the Linux deployment loads `alerts.host.yml`. For host-rule validation also run:

```sh
docker compose run --rm --no-deps --entrypoint promtool prometheus check rules /etc/prometheus/alerts.host.yml
```

The GitHub Actions workflow additionally brings up a disposable local stack and runs the measured disk demo. The first GitHub execution passed, including the measured disk demo: [verification run](https://github.com/dishavpavoor/Devops-project/actions/runs/43746899608). This is additional verification and does not replace running Jenkins.

If a deployment smoke test fails, inspect logs before proceeding. Roll back by loading the previous saved image and setting `IMAGE_TAG` to that build number; no automatic rollback is claimed.

## Cleanup

Use `docker compose -f compose.yaml -f compose.linux.yaml down` to stop the host stack while retaining monitoring data. When the assessment is complete, review `terraform plan -destroy` and run `terraform destroy` in the Terraform directory to remove the provisioned EC2 instance/security group. Named Docker volumes disappear when their EC2 disk is removed.
