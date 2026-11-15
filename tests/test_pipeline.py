import csv
import joblib
import pytest
from ml.generate import generate
from ml.train import train
from ml.evaluate import evaluate
from ml.features import load_rows


def test_train_then_evaluate_unseen_runs(tmp_path):
    generate(tmp_path)
    model = tmp_path / "model.joblib"
    metadata = train(tmp_path / "train.csv", model)
    result = evaluate(model, tmp_path / "test.csv", tmp_path / "reports")
    assert metadata["synthetic"] is True
    assert metadata["training_windows"] > 100
    assert result["recall"] > .7
    assert result["normal_false_positive_rate"] < .15
    assert result["evaluated_windows"] == 924
    assert {r["run_id"] for r in load_rows(tmp_path / "train.csv")}.isdisjoint(
        {r["run_id"] for r in load_rows(tmp_path / "test.csv")})
    assert joblib.load(model)["metadata"]["source_sha256"] == metadata["source_sha256"]


def test_refuse_training_on_anomalies(tmp_path):
    generate(tmp_path)
    with pytest.raises(ValueError, match="normal"):
        train(tmp_path / "test.csv", tmp_path / "bad.joblib")


def test_csv_rejects_percent_and_timezone(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp_utc,host,cpu_pct,ram_pct,disk_used_pct\n2026-01-01T00:00:00,host,20,30,40\n")
    with pytest.raises(ValueError, match="UTC"):
        load_rows(path)


def test_refuse_evaluation_on_training_runs(tmp_path):
    generate(tmp_path)
    model = tmp_path / "model.joblib"
    train(tmp_path / "train.csv", model)
    with pytest.raises(ValueError, match="different"):
        evaluate(model, tmp_path / "train.csv", tmp_path / "report")
