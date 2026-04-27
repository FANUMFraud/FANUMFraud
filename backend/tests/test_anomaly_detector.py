from datetime import UTC, datetime, timedelta

from anomaly_detector import ScoreAnomalyDetector, ScoreObservation


def test_no_anomaly_for_smooth_series() -> None:
    detector = ScoreAnomalyDetector(window_size=6, min_history=4, z_threshold=3.0, min_abs_jump=8.0)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    observations = [
        ScoreObservation(timestamp=start + timedelta(days=index), score=100 - index)
        for index in range(12)
    ]

    anomalies = detector.detect(observations)
    assert anomalies == []


def test_detects_sharp_drop() -> None:
    detector = ScoreAnomalyDetector(window_size=6, min_history=4, z_threshold=3.0, min_abs_jump=8.0)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    scores = [100, 99, 98, 97, 96, 95, 72, 71, 70]
    observations = [
        ScoreObservation(timestamp=start + timedelta(days=index), score=value)
        for index, value in enumerate(scores)
    ]

    anomalies = detector.detect(observations)

    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.direction == "drop"
    assert anomaly.delta == -23.0
    assert anomaly.severity in {"high", "critical"}


def test_detects_sharp_surge() -> None:
    detector = ScoreAnomalyDetector(window_size=6, min_history=4, z_threshold=3.0, min_abs_jump=8.0)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    scores = [50, 49, 48, 47, 46, 45, 69, 68]
    observations = [
        ScoreObservation(timestamp=start + timedelta(days=index), score=value)
        for index, value in enumerate(scores)
    ]

    anomalies = detector.detect(observations)

    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.direction == "surge"
    assert anomaly.delta == 24.0
