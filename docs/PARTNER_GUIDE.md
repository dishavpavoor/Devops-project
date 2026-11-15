# Project explanation and usage guide

## Project description — share these points

- **Project:** Server Early Warning and Resource Anomaly Monitoring. “Sentinel” is the application's internal name.
- **Problem:** A server can run out of disk space before a fixed threshold gives an operator enough time to respond. CPU and memory can also behave unusually.
- **Monitoring:** Collects CPU, RAM and disk utilization from one Linux host using Node Exporter.
- **Forecasting:** Prometheus uses the recent disk trend to estimate whether utilization will reach 95% within a future time window.
- **Machine learning:** A Python service uses Isolation Forest to score unusual combinations of resource features. This is separate from disk forecasting.
- **Dashboard:** Grafana displays current resource use, the disk forecast, anomaly scores, readiness and alert history.
- **Alerts:** Prometheus evaluates rules; Alertmanager groups active alerts. Email/Slack delivery is not configured.
- **Git:** Source code is versioned in the public [Devops-project repository](https://github.com/dishavpavoor/Devops-project).
- **Jenkins:** Runs locally in Docker, checks out main, trains/evaluates the model, runs tests, validates monitoring rules, builds an image and deploys it over SSH.
- **AWS:** The monitoring stack is deployed on an existing Ubuntu 26.04 t3.micro EC2 instance. No second EC2 instance was created by this deployment.
- **Docker:** Runs the Python service, Node Exporter, Prometheus, Grafana and Alertmanager as separate containers.
- **Required tools covered:** Git + Jenkins + AWS + Docker. Terraform and Ansible are additional helpers; Kubernetes is not required.
- **Verified:** Jenkins build 3 succeeded, all 12 Python tests passed, and all 12 dashboard queries were checked against live EC2 data.
- **Experimental result:** Two earlier bounded local disk experiments produced predictive warnings 14 seconds before the sampled 95% crossing. This is a local demo result, not a measured EC2-root-disk exhaustion result.
- **ML limitation:** The deployed image currently uses a synthetic demonstration model. Representative EC2 baseline training and held-out real-host ML evaluation remain necessary before treating anomaly alerts as operationally reliable.

## How the system works

```text
EC2 CPU / RAM / root filesystem
             ↓
       Node Exporter
             ↓
         Prometheus ← Python collector / Isolation Forest score
             ↓                       ↑
      Grafana dashboard       Saved model artifact
             ↓
     Human inspects warnings

Prometheus alert rules → Alertmanager groups active alerts

GitHub → Jenkins → tests + Docker image → SSH deployment to EC2
```

In Linux mode, Prometheus scrapes Node Exporter every 5 seconds. The Python collector reads those node metrics through Prometheus every 2 seconds, computes normalized CPU/RAM/disk percentages and exports them with the model score. Prometheus scrapes that service every 2 seconds. This means repeated values between Node Exporter scrapes are possible.

Each ML window contains 10 consecutive samples, spanning 18 seconds from first to last. For each of CPU, RAM and disk, we calculate mean, standard deviation and slope per second: nine features total. Isolation Forest scores the window against the saved training model. We negate its decision function so **a positive score means unusual behaviour**. It is not a probability of server failure.

The disk forecast uses linear regression over the recent disk percentage. A rising trend projected to reach 95% triggers a predictive warning after its hold period. A separate fixed alert triggers at actual utilization of 90%. These signals answer different questions: disk forecast estimates capacity pressure; ML identifies deviation from the training baseline.

## What each dashboard panel means

| Panel | What it shows | How to interpret it |
|---|---|---|
| Experiment context | Mode, sampling, lookback/forecast windows and model caveat | Read this first so the accelerated local demo is not confused with real-host monitoring. |
| Disk forecast alert | Current state of the predictive disk rule | Clear means no current firing warning. Firing means rising disk use is projected to reach the forecast threshold under the rule's conditions. Missing/stale data requires investigation. |
| ML inference ready | Whether the saved model has a complete fresh window to score | Ready means inference can run. Startup or missing samples require another complete window. The service loads a saved model; it does not train automatically at startup. |
| Metrics exporter | Whether Prometheus can scrape the Python exporter | Up means reachable. Separate freshness/collection alerts cover a reachable exporter that has stopped collecting data. |
| Disk usage and forecast | Actual disk %, projected disk % and the 95% reference line | Compare the actual trend with its extrapolation. A forecast can change when writes slow, stop or files are removed. On EC2 this is the host root filesystem. |
| CPU and memory usage | Percentage of CPU busy and RAM in use | Sustained high values indicate load, but these curves alone do not prove a fault. Linux CPU is averaged over a one-minute rate window; RAM uses available/total memory. |
| ML anomaly score | Resource-window score and the zero threshold | Above zero indicates an outlier relative to the model; below zero indicates an inlier. It is not “percent chance of failure.” The current synthetic model may flag normal EC2 behaviour. |
| Alert history | Firing state over time for predictive disk and 90% baseline alerts | For this single host, 1 means firing and 0 means clear. Compare the first firing time with the observed threshold crossing. ML has its own score/rule; this panel compares the two disk alerts. |

### Local demonstration versus EC2 settings

| Setting | Local accelerated demo | EC2 Linux deployment |
|---|---|---|
| Disk measured | Dedicated 24 MiB tmpfs | Host root filesystem |
| Forecast lookback | 30 seconds | 5 minutes |
| Forecast horizon | 25 seconds | 10 minutes |
| Predicted limit | 95% | 95% |
| Predictive hold | 6 seconds | 30 seconds |
| Fixed threshold | 90%, held for 2 seconds | 90%, held for 10 seconds |
| Disk filling allowed | Only the dedicated tmpfs | Disabled |

## How to use the prepared project on the current Mac

### 1. Start Docker Desktop and Jenkins

From the existing project directory:

```sh
cd /Users/disha/Documents/ChatGPT/DevOps
docker compose --env-file .local/jenkins.env -f compose.jenkins.yaml up -d
```

The `.local` files already exist on this machine and are intentionally excluded from GitHub. A fresh clone needs the setup procedure in [LOCAL_JENKINS.md](LOCAL_JENKINS.md).

### 2. Open the existing EC2 connection

The SSH tunnel may already be running. Try the EC2 dashboard link below first. If unavailable, open a new terminal and run the following, replacing `EC2_PUBLIC_IP` with the instance's current public IP:

```sh
cd /Users/disha/Documents/ChatGPT/DevOps
ssh -i "$HOME/Downloads/Devops_keypair.pem" \
  -o UserKnownHostsFile=.local/jenkins/secrets/known_hosts \
  -o StrictHostKeyChecking=yes \
  -L 3001:localhost:3000 -L 9091:localhost:9090 \
  -L 9094:localhost:9093 -L 8002:localhost:8001 \
  ubuntu@EC2_PUBLIC_IP
```

Leave this terminal open while using the dashboard. If a port is already in use, use the existing tunnel rather than starting a duplicate. Stopping/starting an EC2 instance can change its public IP; verify the new address and host key before reconnecting.

### 3. Open the services

| Service | Address on this Mac | Login |
|---|---|---|
| EC2 Grafana | [localhost:3001/d/server-risk](http://localhost:3001/d/server-risk) | `admin`; password in `.local/jenkins/secrets/grafana_password` |
| Jenkins | [localhost:8080/job/Devops-project](http://localhost:8080/job/Devops-project/) | `admin`; password in `.local/jenkins/secrets/admin_password` |
| EC2 Prometheus alerts | [localhost:9091/alerts](http://localhost:9091/alerts) | Access through SSH tunnel |
| EC2 Alertmanager | [localhost:9094](http://localhost:9094) | Access through SSH tunnel |
| EC2 collector status | [localhost:8002/api/status](http://localhost:8002/api/status) | Read-only API through SSH tunnel |
| Local safe-demo Grafana | [localhost:3000/d/server-risk](http://localhost:3000/d/server-risk) | `admin`; password in the local `.env` |

These localhost addresses work on the machine running the tunnel/controller. They are not public websites. Keep credentials out of shared presentation slides, screenshots, chat and Git.

### 4. Inspect the running cloud project

1. Verify **Metrics exporter** is Up and **ML inference ready** is Ready.
2. Select a recent time range in Grafana and inspect CPU, RAM and disk curves.
3. Confirm that the disk being monitored is the EC2 host root filesystem.
4. View Prometheus Alerts to distinguish normal/inactive rules, pending rules and firing rules.
5. Check the collector status API to see source, freshness and whether the loaded model is synthetic.
6. Open Jenkins build 3 to inspect the successful checkout, tests, image build, deployment and smoke-test stages.

### 5. Demonstrate disk early warning safely

Run this **on the Mac's local demo**, not on EC2:

```sh
cd /Users/disha/Documents/ChatGPT/DevOps
docker compose up -d
python3 -m scripts.demo_report
```

Open the local demo dashboard at port 3000. The command waits for baseline history, writes only to a dedicated 24 MiB tmpfs, holds briefly and removes its own fill file. It records actual alert lead times in `reports/live-demo.json` and fails if the predictive warning does not precede the sampled 95% crossing. Allow about 100 seconds.

An already-firing ML alert is not credited with a warning lead time. The disk forecast drives this demonstration. Never fill the EC2 root filesystem to reproduce the demo.

### 6. Update and redeploy

```sh
git status
# Review your changes and run the relevant tests.
git add path/to/changed-file
git commit -m "Describe the change"
git push origin main
```

In Jenkins choose **Build with Parameters**:

- `DEPLOY=true`
- `DEPLOY_HOST` = the existing EC2 public IP
- `TARGET_PLATFORM=linux/amd64`
- `SMALL_INSTANCE=true`

Wait for **SUCCESS**, then inspect Grafana and `/api/status`. The job can also be followed using `python3 -m scripts.jenkins_run --host EC2_PUBLIC_IP`. Public GitHub source does not make Jenkins or the dashboard public; both remain behind local access/SSH.

## AWS configuration: what is included?

**Yes, AWS deployment configuration is included and has been used to deploy the application to an existing EC2 instance.**

| File/component | Purpose | Actual status |
|---|---|---|
| `compose.linux.yaml` | Node Exporter and real Linux host monitoring | Running on EC2 |
| `compose.small.yaml` | Memory limits and bounded metric retention for t3.micro | Running on EC2 |
| `deploy/ansible/setup.yml` | Docker/Git preparation and small-instance swap setup | Applied successfully to EC2 |
| `Jenkinsfile` + `scripts/deploy.sh` | Build and SSH deployment to AWS | Successful Jenkins build 3 |
| `deploy/terraform/` | Optional reusable EC2/security-group provisioning | Validated and mock-tested; not applied because the instance was launched manually |
| `.local/jenkins.env` and Jenkins credentials | This machine's host/key paths and protected credentials | Local only; intentionally excluded from GitHub |

The existing instance is the deployment target. Do not apply Terraform merely to access that same instance; the supplied configuration creates another one unless you deliberately manage/import resources. AWS CLI keys are not required for the SSH deployment pipeline. Credentials are not embedded in the Docker image or public repository.

## Presentation script — about three minutes

“ Our project is a server early-warning and anomaly-monitoring system. It addresses the problem of operators receiving a disk-space warning too late, and provides a way to inspect unusual resource behaviour.

We collect CPU, memory and disk data from an Ubuntu server hosted on AWS EC2. Node Exporter exposes Linux metrics, Prometheus stores and queries them, and Grafana presents them as a dashboard.

There are two independent signals. First, Prometheus uses the recent disk-utilization trend to forecast capacity pressure. In the cloud configuration, it looks at five minutes of history and projects ten minutes ahead. It warns when rising disk use is projected to reach 95 percent. We compare this with a conventional alert at 90 percent actual usage.

Second, our Python service uses Isolation Forest. It processes ten-sample windows and calculates the mean, standard deviation and rate of change of CPU, RAM and disk use. These nine features produce an anomaly score. A positive score indicates behaviour unlike the training baseline. This detects unusual behaviour; it does not prove that a server will fail.

On the dashboard, CPU and memory show host load. The disk graph compares actual use with the forecast and the 95 percent reference line. The anomaly graph shows the model score against zero. The status panels confirm that metrics are reachable and inference has fresh data. Alert history lets us compare predictive and fixed-threshold warnings.

We used Git and GitHub for version control, Jenkins for the pipeline, Docker for the services, and AWS EC2 for hosting. Jenkins runs locally, checks out our repository, trains and evaluates the model, runs tests, builds the correct Linux image, deploys it to EC2 through SSH, and performs smoke checks. Jenkins build 3 completed successfully, all twelve Python tests passed, and twelve dashboard queries were verified against live EC2 metrics.

For the repeatable experiment, we fill only a small isolated test filesystem in the local demo. Two recorded runs produced a disk forecast warning fourteen seconds before the sampled 95 percent crossing. We did not fill the EC2 root disk. The deployed ML model is currently a synthetic demonstration baseline, so representative real-host training and separate test runs are the next evaluation step.

The result is a working deployment with monitoring, forecasting, an independent ML signal, a tested delivery pipeline and explicit limitations.”

## Suggested two-person split

- **Person 1:** Explain Git, Docker, Node Exporter, Prometheus, Grafana, Jenkins stages and the EC2 deployment. Demonstrate the successful build and dashboard.
- **Person 2:** Explain the data schema, nine features, Isolation Forest score, training/test separation, evaluation results and false-alert limitations. Run the safe disk demo and interpret its measured lead time.
- **Both:** Be able to distinguish forecast from anomaly detection, explain every graph and reproduce the basic workflow.

See [VERIFICATION.md](VERIFICATION.md) and the JSON reports for actual measured evidence. Neither working software nor this script guarantees assessment marks; use the college rubric and describe only results you can reproduce.
