from datetime import datetime, timedelta, timezone
import numpy as np
import pytest
from ml.features import features, windows, WINDOW


def rows(count=20):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [dict(timestamp_utc=(start + timedelta(seconds=i*2)).isoformat(), host="host", run_id="run",
                 cpu_pct=10+i*2, ram_pct=40, disk_used_pct=20) for i in range(count)]


def test_feature_slope_is_per_second():
    vector = features([[10+2*i, 40, 20] for i in range(WINDOW)])
    assert vector[0] == 19
    assert vector[2] == pytest.approx(1)
    assert vector[5] == pytest.approx(0, abs=1e-12)
    assert vector.shape == (9,)


def test_gap_requires_new_complete_window():
    data = rows(30)
    del data[12]
    complete = list(windows(data))
    assert len(complete) == 3 + 8


def test_run_boundary_is_not_joined():
    data = rows(18)
    for row in data[9:]:
        row["run_id"] = "second"
    assert list(windows(data)) == []


def test_reversed_time_rejected():
    data = rows()
    data[8], data[9] = data[9], data[8]
    with pytest.raises(ValueError, match="increase"):
        list(windows(data))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 101])
def test_invalid_percent_rejected(value):
    with pytest.raises(ValueError):
        features([[value, 10, 10]] * WINDOW)
