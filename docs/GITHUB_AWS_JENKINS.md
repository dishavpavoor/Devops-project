# Connect GitHub, Jenkins, Docker and AWS

The project is stored in the public repository [dishavpavoor/Devops-project](https://github.com/dishavpavoor/Devops-project). “Sentinel” is the application's internal name; it is not a separate deployment tool.

Your required toolchain is **Git + Jenkins + AWS + Docker**. Terraform and Ansible are optional automation helpers included in this repository. Kubernetes is not needed.

## Current status

- Git main branch and private GitHub repository: connected.
- Docker monitoring stack: built and tested locally.
- Terraform: configuration validates, and three mocked infrastructure tests pass without creating resources.
- Jenkins: Local Docker controller is running; build 3 successfully tested and deployed to EC2. The separate Ubuntu Jenkins installation playbook remains an optional alternative.
- AWS: Monitoring runs on the existing Ubuntu 26.04 t3.micro instance. It was launched manually; Terraform provisioning was not used.

For the existing t3.micro deployment with Jenkins running locally, see [Local Jenkins → EC2](LOCAL_JENKINS.md). The remaining sections describe alternative provisioning and Jenkins-host arrangements.

## 1. Work with Git

Each teammate can clone the repository:

```sh
git clone https://github.com/dishavpavoor/Devops-project.git
cd Devops-project
git switch -c your-feature-branch
# Edit and test your changes.
git add path/to/changed-file
git commit -m "Describe the change"
git push -u origin your-feature-branch
```

Open a pull request, review it together and merge to main. Keep credentials, private keys, `.env`, model binaries, Terraform state and local environments out of commits. The checked-in example files contain placeholders only. Local host calibration/model binaries are intentionally not uploaded; a fresh checkout builds the reproducible synthetic demonstration model.

## 2. Supply AWS settings locally

Configure an AWS CLI profile on your machine. Do not send access keys or secret keys through chat or Git. Terraform can use the normal AWS credential chain or the optional `aws_profile` variable.

Non-secret settings needed:

| Setting | Example/meaning |
|---|---|
| `region` | `us-east-1` (N. Virginia) |
| `aws_profile` | Name of your local profile, if using one |
| `vpc_id` | Existing VPC ID |
| `subnet_id` | Public subnet in that VPC, with an internet-gateway route |
| `key_name` | Existing EC2 key-pair name in that region |
| `admin_cidr` | Your current public IPv4 address followed by `/32` |

For a single classroom-demo EC2 host running both Jenkins and monitoring, select `instance_type = "t3.medium"` and `root_volume_gb = 50` to leave build capacity. This is a paid configuration unless your own account credits cover it; check current AWS pricing. A separate Jenkins machine can also deploy to a smaller monitoring instance, provided its SSH access is explicitly allowed.

```sh
cp deploy/terraform/terraform.tfvars.example deploy/terraform/terraform.tfvars
# Edit values, including optional aws_profile.
terraform -chdir=deploy/terraform init
terraform -chdir=deploy/terraform validate
terraform -chdir=deploy/terraform test
terraform -chdir=deploy/terraform plan
terraform -chdir=deploy/terraform apply
```

`terraform test` uses mocks. `plan` and `apply` use your real account; `apply` creates billable infrastructure. Terraform supplies an encrypted Ubuntu 24.04 EC2 instance, IMDSv2, and SSH-only inbound access. Grafana and Jenkins are reached over SSH tunnels.

## 3. Prepare the EC2 host and install Jenkins

Create local inventories from the examples and replace the IP/key path:

```sh
cp deploy/ansible/inventory.ini.example deploy/ansible/inventory.ini
cp deploy/ansible/jenkins.ini.example deploy/ansible/jenkins.ini
ansible-playbook -i deploy/ansible/inventory.ini deploy/ansible/setup.yml
ansible-playbook -i deploy/ansible/jenkins.ini deploy/ansible/jenkins.yml
```

The optional Jenkins installer uses Java 21 and the official Jenkins stable package repository, following the [Jenkins Ubuntu instructions](https://www.jenkins.io/doc/book/installing/linux/). It installs Git, Python 3.12, Docker and Compose and binds Jenkins to localhost. Run it on a project-owned host: Jenkins' Docker access allows privileged control of that machine.

Open a tunnel from your laptop, adding your actual key/IP:

```sh
ssh -i ~/.ssh/your-key.pem \
  -L 8080:localhost:8080 -L 3000:localhost:3000 \
  -L 9090:localhost:9090 -L 9093:localhost:9093 \
  -L 8001:localhost:8001 ubuntu@EC2_PUBLIC_IP
```

Open `http://localhost:8080`. Retrieve the initial password on the host with `sudo cat /var/lib/jenkins/secrets/initialAdminPassword`, install suggested plugins, and create your Jenkins administrator. Required plugins include Git, Pipeline, Credentials Binding and JUnit.

For a single-user classroom demo, configure the built-in node with one executor and the label `docker`. A shared Jenkins installation should use a separate build agent with that label and the same build dependencies.

## 4. Prepare deployment configuration and Jenkins credentials

On EC2, create `/opt/sentinel/.env` locally:

```dotenv
GRAFANA_ADMIN_PASSWORD=choose-a-strong-password-here
HOST_ID=ec2-monitor
MODEL_PATH=/app/artifacts/model.joblib
```

Use `chmod 600 /opt/sentinel/.env`, and ensure the deployment SSH user owns it. The pipeline preserves that file. The initial model is synthetic; calibrate on the new host's normal data using the main README before interpreting ML alerts.

Create the following Jenkins credentials:

| ID | Type | Purpose |
|---|---|---|
| `sentinel-github` | Username/password with an appropriate GitHub token, or a read-only SSH deploy key | Checkout of the private GitHub repository |
| `sentinel-grafana-password` | Secret text | A password for Compose configuration validation |
| `sentinel-ec2-ssh` | SSH username/private key | SSH user `ubuntu` and a key authorized on the deployment host |
| `sentinel-known-hosts` | Secret file | Verified SSH host key entry for the deployment hostname |

Keep tokens and private-key contents inside Jenkins credentials. They are not pipeline parameters. A GitHub SSH deploy key is separate from your EC2 access key pair.

When Jenkins and monitoring share one EC2 machine, use `DEPLOY_HOST=localhost`. The deployment key must authenticate as `ubuntu` on localhost, and `sentinel-known-hosts` must contain the verified localhost host key. Verify host fingerprints against the EC2 host's own `/etc/ssh/ssh_host_ed25519_key.pub`; do not bypass host-key checking. This avoids needing a public SSH connection from the instance back to itself.

If Jenkins is on another machine, use the EC2 DNS/IP, verify that host key and ensure the EC2 security group allows the Jenkins agent's source IP as well as your administrative access.

## 5. Create and execute the Jenkins pipeline

1. New Item → **Pipeline**, name `Devops-project`.
2. Pipeline definition → **Pipeline script from SCM**, SCM → **Git**.
3. Repository URL → `https://github.com/dishavpavoor/Devops-project.git`; choose the matching GitHub credential. Use the SSH repository URL instead if using an SSH deploy key.
4. Branch → `*/main`; script path → `Jenkinsfile`.
5. Run **Build Now** once. This creates job parameters and verifies training, tests, rule validation and image build.
6. Run **Build with Parameters**, set `DEPLOY=true`, and set `DEPLOY_HOST=localhost` for the single-EC2 setup.
7. Confirm deployment and smoke-test stages pass. Open Grafana through your tunnel to inspect EC2 metrics.

The pipeline transfers a tagged Docker image and deployment files over verified SSH; it does not need a container registry or AWS access keys inside Jenkins. Terraform provisions the host before this pipeline runs.

The first run may fail if the agent dependencies or credentials have not been supplied. Inspect and resolve the actual stage failure before claiming a successful CI/CD deployment.

## Evidence for your project

Capture the Git commit history, the private repository, a successful Jenkins pipeline including deployment, the running AWS instance and Grafana displaying the Linux host's resources. The GitHub Actions workflow is an additional check; it does not replace the mandatory Jenkins run.

Stop/review cloud resources after the demonstration. Use `terraform plan -destroy` and `terraform destroy` when ready to remove the infrastructure. Terraform's local state is excluded from Git; keep it safely available for managing/destroying the created resources.
