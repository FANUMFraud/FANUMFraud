from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Sequence


@dataclass(frozen=True)
class ScoreObservation:
    timestamp: datetime
    score: float
    article_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _to_utc(self.timestamp))
        object.__setattr__(self, "score", _clamp(float(self.score), 0.0, 100.0))


@dataclass(frozen=True)
class ScoreAnomaly:
    timestamp: datetime
    previous_timestamp: datetime
    previous_score: float
    current_score: float
    delta: float
    robust_z: float
    direction: str
    severity: str
    article_id: int | None = None


class ScoreAnomalyDetector:
    """Detect abrupt score jumps using robust z-score over score deltas."""

    def __init__(
        self,
        window_size: int = 14,
        min_history: int = 6,
        z_threshold: float = 3.5,
        min_abs_jump: float = 8.0,
        epsilon: float = 1e-9,
    ) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be > 0")
        if min_history <= 1:
            raise ValueError("min_history must be > 1")
        if z_threshold <= 0:
            raise ValueError("z_threshold must be > 0")
        if min_abs_jump <= 0:
            raise ValueError("min_abs_jump must be > 0")

        self.window_size = int(window_size)
        self.min_history = int(min_history)
        self.z_threshold = float(z_threshold)
        self.min_abs_jump = float(min_abs_jump)
        self.epsilon = float(epsilon)

    def detect(self, observations: Sequence[ScoreObservation]) -> list[ScoreAnomaly]:
        if len(observations) < self.min_history + 2:
            return []

        ordered = sorted(observations, key=lambda item: item.timestamp)
        deltas = [ordered[index].score - ordered[index - 1].score for index in range(1, len(ordered))]
        anomalies: list[ScoreAnomaly] = []

        for index, delta in enumerate(deltas, start=1):
            baseline = self._baseline_deltas(deltas, index)
            if len(baseline) < self.min_history:
                continue

            median_delta = median(baseline)
            mad = _mad(baseline, median_delta)
            robust_z = _robust_z(delta, median_delta, mad, self.epsilon)

            abs_delta = abs(delta)
            if abs_delta < self.min_abs_jump:
                continue
            if abs(robust_z) < self.z_threshold:
                continue

            previous = ordered[index - 1]
            current = ordered[index]
            anomalies.append(
                ScoreAnomaly(
                    timestamp=current.timestamp,
                    previous_timestamp=previous.timestamp,
                    previous_score=round(previous.score, 2),
                    current_score=round(current.score, 2),
                    delta=round(delta, 2),
                    robust_z=robust_z,
                    direction="drop" if delta < 0 else "surge",
                    severity=_severity(abs_delta, abs(robust_z)),
                    article_id=current.article_id,
                )
            )

        return anomalies

    def _baseline_deltas(self, deltas: Sequence[float], current_index: int) -> list[float]:
        end = current_index - 1
        start = max(0, end - self.window_size)
        baseline = list(deltas[start:end])
        if len(baseline) >= self.min_history:
            return baseline
        return list(deltas[:end])


def detect_anomalies(
    observations: Sequence[ScoreObservation],
    detector: ScoreAnomalyDetector | None = None,
) -> list[ScoreAnomaly]:
    active_detector = detector or ScoreAnomalyDetector()
    return active_detector.detect(observations)


def _mad(values: Sequence[float], med: float) -> float:
    return median([abs(value - med) for value in values])


def _robust_z(value: float, med: float, mad: float, epsilon: float) -> float:
    if mad <= epsilon:
        if abs(value - med) <= epsilon:
            return 0.0
        return float("inf") if value > med else float("-inf")
    return 0.6745 * (value - med) / (mad + epsilon)


def _severity(abs_delta: float, abs_robust_z: float) -> str:
    if abs_delta >= 25.0 or abs_robust_z >= 8.0:
        return "critical"
    if abs_delta >= 15.0 or abs_robust_z >= 5.0:
        return "high"
    return "medium"


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


__all__ = [
    "ScoreObservation",
    "ScoreAnomaly",
    "ScoreAnomalyDetector",
    "detect_anomalies",
]
