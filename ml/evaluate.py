"""Held-out window scores. No fitting or threshold tuning on the test set."""
import argparse
import csv
import json
from pathlib import Path
import joblib
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from ml.features import load_rows, windows, VERSION, INTERVAL, WINDOW


def evaluate(model_path, csv_path, output):
    bundle = joblib.load(model_path)  # Only load your own trusted model artifacts.
    metadata = bundle["metadata"]
    if (metadata["feature_version"], metadata["interval"], metadata["window"]) != (VERSION, INTERVAL, WINDOW):
        raise ValueError("Incompatible model feature contract")
    source_rows = load_rows(csv_path)
    training_runs = {tuple(run) for run in metadata["training_runs"]}
    test_runs = {(r["host"], r.get("run_id", "default")) for r in source_rows}
    if training_runs & test_runs:
        raise ValueError("Evaluation must use different host/run IDs from training")
    rows = list(windows(source_rows))
    if not rows:
        raise ValueError("No complete evaluation windows")
    scores = -bundle["model"].decision_function([vector for _, vector in rows])
    truth = [int(row["label"]) for row, _ in rows]
    predicted = [int(score > 0) for score in scores]
    precision, recall, f1, _ = precision_recall_fscore_support(truth, predicted, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(truth, predicted, labels=[0, 1]).ravel()
    normal = [i for i, (row, _) in enumerate(rows) if row.get("scenario") == "normal"]
    result = dict(dataset=str(csv_path), synthetic=all(row["host"] == "synthetic-demo" for row, _ in rows),
                  evaluated_windows=len(rows), precision=float(precision), recall=float(recall), f1=float(f1),
                  confusion_matrix=dict(tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp)),
                  normal_false_positive_rate=sum(predicted[i] for i in normal) / len(normal) if normal else None,
                  note="Window labels use the final sample. Overlapping windows are correlated. These are offline scores, not alert precision or proof of real failure prediction.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation.json").write_text(json.dumps(result, indent=2) + "\n")
    with (output / "scores.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp_utc", "run_id", "scenario", "label", "anomaly_score", "predicted"])
        for (row, _), score, pred in zip(rows, scores, predicted):
            writer.writerow([row["timestamp_utc"], row.get("run_id"), row.get("scenario"), row["label"], score, pred])
    text = f"# Held-out evaluation\n\nSynthetic fixture: {result['synthetic']}. Windows: {len(rows)}.\n\n| Precision | Recall | F1 | Normal false-positive rate |\n|---|---|---|---|\n|{precision:.3f}|{recall:.3f}|{f1:.3f}|{result['normal_false_positive_rate']}|\n\n{result['note']}\n\nTraining and test runs use separate random seeds and run IDs. Replace these fixtures with real normal training runs and separately recorded test runs before making performance claims.\n"
    (output / "evaluation.md").write_text(text)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="artifacts/model.joblib")
    parser.add_argument("--csv", default="data/test.csv")
    parser.add_argument("--output", default="reports")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.model, args.csv, args.output), indent=2))
