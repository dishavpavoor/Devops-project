import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import joblib
import sklearn
from sklearn.ensemble import IsolationForest
from ml.features import VERSION, INTERVAL, WINDOW, NAMES, load_rows, windows


def train(csv_path, output):
    rows = load_rows(csv_path)
    if any(row.get("label", "0") != "0" or row.get("scenario", "normal") != "normal" for row in rows):
        raise ValueError("Train only on explicitly selected normal periods")
    matrix = [vector for _, vector in windows(rows)]
    if len(matrix) < 100:
        raise ValueError("Need at least 100 complete normal windows")
    model = IsolationForest(n_estimators=200, contamination=.02, random_state=42, n_jobs=1)
    model.fit(matrix)
    metadata = dict(feature_version=VERSION, interval=INTERVAL, window=WINDOW,
                    feature_names=NAMES, training_windows=len(matrix), sklearn=sklearn.__version__,
                    trained_at=datetime.now(timezone.utc).isoformat(),
                    source_sha256=hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
                    training_runs=sorted({(r["host"], r.get("run_id", "default")) for r in rows}),
                    source=str(csv_path), synthetic=all(r["host"] == "synthetic-demo" for r in rows))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(dict(model=model, metadata=metadata), output)
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/train.csv")
    parser.add_argument("--output", default="artifacts/model.joblib")
    args = parser.parse_args()
    print(json.dumps(train(args.csv, args.output), indent=2))
