# Verification record

Initial local checks: 15 November 2026. Cloud deployment and final checks: 16 November 2026 (Asia/Kolkata). Actual evidence is distinguished from supplied deployment configuration.

## Observed checks

- Python feature and pipeline tests passed, including per-second slopes, gap/run boundaries, invalid values, training-only-normal enforcement and separate evaluation-run enforcement.
- Prometheus configuration and rule syntax passed `promtool` validation.
- Rule tests passed for rising disk warning before a fixed threshold, no forecast on a stable disk, and stalled collection detection.
- Docker image built successfully and the local stack started.
- Smoke test passed: saved model ready, Grafana healthy, exporter scraped, rule evaluations healthy.
- Terraform validation and three mock-provider tests passed; Terraform was not applied. The host Ansible playbook was subsequently applied successfully to EC2 (11 successful tasks, no failures).

## First live disk-fill experiment

The experiment used actual tmpfs writes and queried Prometheus alert history at a 2-second resolution:

| Observation | Unix time | Lead relative to first sampled >=95% |
|---|---|---|
| Experiment start | 1794760159 | — |
| Predictive disk alert first firing | 1794760191 | **14 seconds before** |
| First sampled disk >=95% | 1794760205 | 0 |
| 90% threshold alert first firing | 1794760207 | **2 seconds after** |

The predictive alert passed the acceptance criterion. The fixed threshold was late in this accelerated run because its small remaining write-time margin competes with scrape, evaluation and hold delays. Repeat runs can vary; these results are not a reliability guarantee.

The resource anomaly alert was already active when this experiment began. Its apparent 46-second lead is **not credited**. This demonstrates a synthetic-to-host baseline mismatch, not successful ML prediction. The updated reporter explicitly identifies preexisting alerts and assigns them no lead time. Retrain on real normal host data before reporting ML alert quality.

## Offline fixture evaluation

924 held-out synthetic windows: precision 0.861, recall 0.947, F1 0.902; normal-run false-positive rate 0.0303. Confusion counts: TN 728, FP 26, FN 9, TP 161. See `reports/evaluation.json` for exact values. Separate seeds, runs and time periods are used for training/test fixtures. Real-host held-out ML evaluation remains work for the project team.

## Initial local-host calibration

After the synthetic-model experiment, 297 aligned real samples were exported from approximately ten minutes of normal local operation. Maximum demo disk utilization in that recording was 0%. Training produced 279 complete windows after gap resets, saved as `artifacts/host.joblib` with metadata in `artifacts/host.json`. The local `.env` selects this model. This single recording is initial calibration, not broad held-out real-host ML validation.

## Final repeat with local model

The final rebuilt stack passed its smoke test. The second disk experiment again measured **14 seconds of predictive lead time** (first firing Unix 1794764521; first sampled >=95% Unix 1794764535). The threshold baseline fired at Unix 1794764537, 2 seconds late. Neither disk alert was active before the run. The local-host ML alert did **not** fire in this experiment; no ML warning lead time is claimed. The final report is `reports/live-demo.json`.

A baseline with constant empty-disk features may not teach Isolation Forest to recognize subsequent disk changes: constant features offer no useful training split. The separate linear forecast still detects capacity growth. This illustrates why representative training variation and independent real test runs are necessary, and why the project does not treat anomaly detection as its disk prediction mechanism.

Final verification: 12 Python tests passed; demo and host rule syntax passed; Prometheus unit-rule tests passed; both Compose modes resolved successfully; Ansible syntax and Terraform formatting checks passed. Both local experiments cleaned up their demo fill file.

## GitHub and infrastructure configuration checks

The private repository is [dishavpavoor/Devops-project](https://github.com/dishavpavoor/Devops-project). Its [first verification workflow](https://github.com/dishavpavoor/Devops-project/actions/runs/43746899608) passed on GitHub, including model training/evaluation, Python tests, Prometheus rule validation, container startup, smoke checks and the disk warning experiment.

Terraform provider initialization and configuration validation passed. Three mock-provider tests passed for encrypted disk/IMDSv2/SSH restrictions, rejecting public SSH, and rejecting mismatched VPC/subnet settings. These tests did not create AWS resources. The new Jenkins Ubuntu installation playbook passed Ansible syntax checking; it has not yet been applied to an EC2 host.

## Successful EC2 deployment through Jenkins

- The user-launched Ubuntu 26.04 t3.micro instance now runs Node Exporter, the Python collector/model service, Prometheus, Grafana and Alertmanager.
- Jenkins runs locally in Docker so the small EC2 instance does not also host the controller/build tools.
- Jenkins build **3** finished **SUCCESS** in about 111 seconds and deployed Git revision `c9c8ec0a3b7b12f22ad9d934041dd6fa134ea5ef` for `linux/amd64`.
- The pipeline ran model training/evaluation, all **12 Python tests**, Prometheus config/rule checks, image build, SSH transfer, container deployment and the smoke test.
- The final read-only EC2 verification checked all **12 dashboard expressions**, confirmed fresh Node Exporter data and matched the monitored disk percentage to the actual root filesystem within one percentage point.
- HTTP service ports are bound to the host loopback interface and reached from the Mac through SSH tunnels. Jenkins is also published only on localhost.
- The small-instance profile limits service memory and Prometheus retention to 24 hours / 256 MB. A bounded 512 MiB swap file was configured; the instance was not resized.
- See `reports/jenkins-build.json` and `reports/ec2-verification.json` for the recorded result and sampled metrics. Passwords, private-key contents and local controller state are not included.

## Remaining evaluation and unrun components

Terraform provisioning; applying the optional Jenkins-on-Ubuntu installer; external email/Slack delivery; representative EC2 baseline calibration and real held-out ML evaluation; production reliability or arbitrary failure prediction. The deployed image currently contains the clearly labeled synthetic ML model. Cloud verification did not fill the root filesystem or claim a measured cloud disk-exhaustion lead time.
