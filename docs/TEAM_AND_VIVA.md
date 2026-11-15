# Two-person delivery and viva guide

## Ownership

| Teammate | Main ownership | Demonstrable contribution |
|---|---|---|
| Person 1 | Compose, Prometheus rules, Grafana, Alertmanager, Jenkins, Terraform, Ansible | Explain collection → storage → dashboard → alert flow; run the disk demo; show rule tests and deployment pipeline |
| Person 2 | CSV contract, feature extraction, model training, inference, evaluation | Explain Isolation Forest and the nine features; retrain on recorded normal runs; interpret confusion matrix, false positives and model limitations |

Both should know how to start/stop the stack, distinguish prediction from anomaly detection, explain sampling effects, and reproduce a result. Use real commits and a short contribution log as you work through the code; do not invent development history.

## Suggested 8-minute presentation

1. **Problem (45 seconds):** fixed thresholds can leave little time during rapid disk growth.
2. **Architecture (60 seconds):** show the report diagram and describe the two independent signals.
3. **Working system (60 seconds):** show CPU/RAM/disk charts and API readiness; identify the demo filesystem and data source.
4. **Live experiment (2 minutes):** start `python -m scripts.demo_report`, show the disk trend, predictive alert and baseline alert; show the resulting measured lead times.
5. **ML evidence (60 seconds):** show held-out evaluation and explain why synthetic results are not real-host validation.
6. **Engineering (60 seconds):** show tests, Jenkins stages, deployment configuration and secret handling.
7. **Limitations (45 seconds):** linear-trend assumptions, host drift, one host and no claim to predict arbitrary failures.
8. **Contributions and next steps (30 seconds):** each teammate states their work and what they verified.

Before the demo, retrain on at least 10 minutes of normal data from the machine being shown, restart the monitor with that model, verify it is ready, and check whether it is already emitting anomalies. Keep the original synthetic evaluation as a clearly labeled fixture result. Record separate test runs for your final ML comparison.

## Questions to prepare

**Does Isolation Forest predict server failure?** It detects feature windows unlike the normal baseline. Disk forecasting supplies the measurable predictive component; anomaly scores alone do not establish future failure.

**Why not only a 90% threshold?** A threshold ignores rate of change. A linear forecast can warn sooner during sustained growth, but may be wrong if the workload changes.

**Why Isolation Forest?** It can learn normal multivariate behaviour without labeled failure examples. It is sensitive to the training distribution and requires evaluation on the target workload.

**What does the score mean?** This implementation negates the decision function. Positive means outlier relative to the fitted threshold. It is not a percentage confidence.

**How did you prevent train/test leakage?** Separate fixture runs, seeds and IDs; fitting occurs only on training windows. For real data, split whole chronological runs before extracting windows.

**Why do baseline alerts sometimes arrive after the 95% crossing?** In the accelerated 24 MiB demo, the final few writes happen quickly. Scraping, rule evaluation and the hold delay can consume that short margin.

**What happens when monitoring breaks?** Exporter-down and stale-collection alerts cover distinct faults. Freshness checks prevent old values from appearing to be fresh warnings.

**How would you make it production-ready?** Collect representative real data, validate forecast windows per workload, configure notifications, add access controls/TLS and drift monitoring, then test operationally.

## Is this suitable for 60 marks?

This is a substantial project scope, but only your actual rubric determines marks. Use the following evidence checklist rather than promising a score:

- Explain the problem and measurable acceptance criteria.
- Demonstrate the system end to end on the day.
- Include measured predictive-vs-threshold results and acknowledge failed/late alerts.
- Collect real normal and held-out test runs; report false positives honestly.
- Show tests, reproducibility, pipeline and deployment artifacts.
- Have both teammates explain their code and design tradeoffs.
- Include the report, references, screenshots and actual contribution history.

If your rubric specifically requires deep learning, custom algorithms, an actual cloud deployment or a dedicated frontend, this implementation alone does not establish those requirements.
