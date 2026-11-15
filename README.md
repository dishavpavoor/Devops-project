# Devops Project — Server Early Warning

GitHub repository: [dishavpavoor/Devops-project](https://github.com/dishavpavoor/Devops-project). Sentinel is the application's internal name.

For a shareable description, presentation script, graph explanations and usage steps, read the [partner guide](docs/PARTNER_GUIDE.md).

For an existing small EC2 instance, use the [local Jenkins deployment guide](docs/LOCAL_JENKINS.md). For other setups, follow the [integration guide](docs/GITHUB_AWS_JENKINS.md). The required tools are **Git + Jenkins + AWS + Docker**.

A complete single-host monitoring project with live CPU/RAM/disk charts, disk capacity forecasting, independent ML anomaly detection, a repeatable bounded experiment, model evaluation, CI/CD and EC2 deployment configuration.

**Local demo verified:** the predictive disk alert fired **14 seconds before the sampled 95% crossing** in the first recorded experiment. The 90% baseline fired **2 seconds after** that crossing. These accelerated-demo results depend on timing and fill rate; they are not a production SLA. See [verification](docs/VERIFICATION.md).

## Start here

Requires Docker Desktop on macOS/Windows, or Docker Engine + Compose on Linux. Docker Desktop monitors its Linux environment; it does not measure the macOS host directly.

```sh
cp .env.example .env
# Choose a Grafana admin password in .env before starting.
docker compose up --build -d
python3 -m scripts.smoke
```

If `.env` already exists, keep it. This workspace already has a generated password and uses `artifacts/host.joblib`, an initial baseline trained on 297 locally recorded normal samples. Fresh checkouts use the synthetic model until calibrated. Grafana username is **admin**; the password is the `GRAFANA_ADMIN_PASSWORD` value in `.env`. Changing that value after Grafana initializes its persistent volume does not reset an existing Grafana user's password.

| Service | Local address |
|---|---|
| Grafana dashboard | [Open Sentinel](http://localhost:3000/d/server-risk) |
| Prometheus alerts | [Open alerts](http://localhost:9090/alerts) |
| Alertmanager | [Open grouped alerts](http://localhost:9093) |
| API documentation | [Open API](http://localhost:8001/docs) |
| Current sample/model provenance | [Open status](http://localhost:8001/api/status) |

Allow 20–40 seconds for model-window readiness. `scripts.smoke` waits up to 180 seconds and checks model readiness, Grafana health, Prometheus scraping and rule health. Ports are bound to localhost. Grafana, Prometheus and Alertmanager retain data in named Docker volumes.

## Demonstrate predictive warning

```sh
python3 -m scripts.demo_report
```

This waits for a baseline, writes gradually to a dedicated **24 MiB tmpfs**, holds near 96% for 12 seconds, cleans up its own file and creates `reports/live-demo.json`. It fails if no predictive warning is observed before the sampled 95% crossing. Budget roughly 100 seconds for the full command.

Watch **Disk usage and forecast** and **Alert history** in Grafana. The experiment measures actual Prometheus firing times, including scrape/evaluation delays. An alert already firing before the experiment does not earn a warning lead time. The ML score and disk forecast are separate signals.

The demo uses no privileged container, loop device or host-disk filling. Disk-fill execution is disabled in Linux host mode. Keep the terminal open so the script can clean up. If the process is force-killed, recreate only the monitor to clear its tmpfs:

```sh
docker compose up -d --force-recreate monitor
```

Only one fill process can run at a time. To stop the stack while keeping monitoring history:

```sh
docker compose down
```

## Train and evaluate the ML component

For host-side ML commands, use **Python 3.12**:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ml.train
.venv/bin/python -m ml.evaluate
.venv/bin/python -m pytest -q
```

This authoring workspace also contains a ready-to-use `.venv312`; use `.venv312/bin/python` for the commands above if you do not have Python 3.12 on your PATH. The default CSV fixtures are already included. Regenerate them deterministically with `python -m ml.generate` only when you intend to replace the synthetic fixtures.

Outputs:

- `artifacts/model.joblib`: trusted model bundle, excluded from Git.
- `artifacts/model.json`: training provenance, feature contract and source hash.
- `reports/evaluation.json` and `reports/evaluation.md`: held-out fixture results.
- `reports/scores.csv`: per-window predictions.

The initial image trains a **synthetic demonstration model at build time**. It never automatically learns from potentially anomalous startup samples. Synthetic evaluation currently gives precision **0.861**, recall **0.947**, F1 **0.902**, and a **3.03% normal-window false-positive rate**. This is not a validated real-host performance claim. The synthetic model can flag a real host's normal workload continuously; retrain before interpreting live ML warnings.

### Replace the demo model with a real baseline

First record at least 10 minutes of normal activity, with no disk-fill process running:

```sh
python3 -m scripts.export_metrics --seconds 600 --output data/live-normal.csv --scenario normal --label 0
.venv/bin/python -m ml.train --csv data/live-normal.csv --output artifacts/host.joblib
```

Set `MODEL_PATH=/models/host.joblib` in `.env`, then recreate the monitor. Models under `artifacts/` are mounted read-only at `/models`. `/api/status` exposes whether the loaded model is synthetic and its training provenance. Joblib files must come from a trusted source.

Collect separate normal, spike and growth test runs and label their actual anomaly intervals before evaluation. Exporting with `--label 1` assigns that label to every exported row, so only use it for a precisely bounded anomalous segment; manually label mixed runs correctly. Run IDs are created by the exporter; evaluation rejects training-run IDs to reduce leakage. Split whole runs chronologically before feature extraction. Do not tune a threshold on the same test set you report.

```sh
.venv/bin/python -m ml.evaluate --model artifacts/host.joblib --csv data/heldout.csv --output reports/real
```

The shared schema is `timestamp_utc,host,cpu_pct,ram_pct,disk_used_pct`, sampled every 2 seconds. Ten samples form a window; mean, standard deviation and slope per second for each resource give nine features. Invalid percentages, non-UTC timestamps and reversed time are rejected; windows reset after gaps. See [project report](docs/PROJECT_REPORT.md) for metric definitions and limitations.

## Linux host monitoring

On a real Linux host, use:

```sh
docker compose -f compose.yaml -f compose.linux.yaml up --build -d
python3 -m scripts.smoke
```

This adds Node Exporter, monitors the root filesystem and uses a 5-minute trend / 10-minute forecast. It takes up to a minute to establish CPU rate history. It supports exactly one Node Exporter target initially. The disk fill command is disabled. Export and train on this mode's normal data; demo-mode CPU semantics differ from Node Exporter CPU rates.

The default demo uses a 30-second trend / 25-second horizon to make the presentation short. Both modes require fresh samples for resource alerts and provide separate unavailable/stale alerts. Prometheus evaluates rules; Grafana visualizes them. Alertmanager groups the alerts locally. **No email or Slack messages are sent** until you configure a real receiver in `alertmanager/alertmanager.yml`.

## Validation and deployment

```sh
docker compose config --quiet
docker compose run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/test_rules.yml
docker compose run --rm --no-deps --entrypoint promtool prometheus check rules /etc/prometheus/alerts.host.yml
```

- [Deployment guide](docs/DEPLOYMENT.md): Terraform, Ubuntu/Ansible, SSH access, Jenkins credentials and optional EC2 deployment.
- `Jenkinsfile`: train → evaluate → test → validate rules → build → optional deploy → smoke test.
- `.github/workflows/ci.yml`: tests plus disposable stack and measured disk demo.
- [Verification record](docs/VERIFICATION.md): checks actually performed and unrun deployment components.

The existing EC2 instance now runs the Linux monitoring stack. Local Jenkins build **3** successfully deployed Git revision `c9c8ec0` and passed smoke checks; all 12 dashboard queries were verified against live EC2 metrics. See [verification](docs/VERIFICATION.md). Terraform was not applied, no additional instance was created, and external email/Slack delivery remains unconfigured.

## Two-person submission

Read the [team and viva guide](docs/TEAM_AND_VIVA.md) for ownership, presentation flow, questions and evidence needed for a 60-mark assessment. This scope can support a substantial submission; marks depend on your rubric, real validation and both teammates understanding the implementation.

```text
monitor/            Collector, inference API, Dockerfile, bounded demo
ml/                 Shared features, fixtures, training, evaluation
prometheus/         Demo/host configurations, alerts and rule tests
grafana/            Provisioned datasource and dashboard
alertmanager/       Local alert grouping
scripts/            Smoke test, CSV export, measured demo report
tests/              Feature and ML-pipeline tests
deploy/             Terraform and Ansible
docs/               Project report, verification, deployment and viva guide
```
