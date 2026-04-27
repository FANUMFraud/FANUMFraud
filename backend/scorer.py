from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import exp, log
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RiskSignal:
    timestamp: datetime
    risk_score: float
    confidence: float = 0.7
    sentiment: str = "negative"
    source_weight: float = 1.0
    article_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _to_utc(self.timestamp))
        object.__setattr__(self, "risk_score", _clamp(float(self.risk_score), 0.0, 100.0))
        object.__setattr__(self, "confidence", _clamp(float(self.confidence), 0.0, 1.0))
        object.__setattr__(self, "source_weight", _clamp(float(self.source_weight), 0.1, 3.0))
        object.__setattr__(self, "sentiment", str(self.sentiment).lower().strip())


@dataclass(frozen=True)
class ScorePoint:
    timestamp: datetime
    score: float
    active_risk: float
    signal_count: int


class ReputationScorer:
    """Reputation score model using exponential decay over risk events."""

    SENTIMENT_FACTORS = {
        "negative": 1.0,
        "mixed": 0.7,
        "neutral": 0.25,
        "positive": -0.25,
    }

    def __init__(
        self,
        half_life_days: float = 45.0,
        min_score: float = 0.0,
        max_score: float = 100.0,
        confidence_floor: float = 0.35,
    ) -> None:
        if half_life_days <= 0:
            raise ValueError("half_life_days must be > 0")
        if max_score <= min_score:
            raise ValueError("max_score must be greater than min_score")

        self.half_life_days = float(half_life_days)
        self.min_score = float(min_score)
        self.max_score = float(max_score)
        self.confidence_floor = _clamp(float(confidence_floor), 0.0, 1.0)
        self._lambda = log(2.0) / self.half_life_days

    def decay_multiplier(self, age_days: float) -> float:
        return exp(-self._lambda * max(age_days, 0.0))

    def signal_impact(self, signal: RiskSignal) -> float:
        sentiment_factor = self.SENTIMENT_FACTORS.get(signal.sentiment, self.SENTIMENT_FACTORS["neutral"])
        confidence_factor = self.confidence_floor + ((1.0 - self.confidence_floor) * signal.confidence)
        return signal.risk_score * sentiment_factor * confidence_factor * signal.source_weight

    def decayed_impact(self, signal: RiskSignal, as_of: datetime) -> float:
        normalized_as_of = _to_utc(as_of)
        age_days = (normalized_as_of - signal.timestamp).total_seconds() / 86_400.0
        if age_days < 0:
            return 0.0
        return self.signal_impact(signal) * self.decay_multiplier(age_days)

    def score_at(self, signals: Sequence[RiskSignal], as_of: datetime | None = None) -> float:
        point = self.point_at(signals, as_of=as_of)
        return point.score

    def point_at(self, signals: Sequence[RiskSignal], as_of: datetime | None = None) -> ScorePoint:
        snapshot = _to_utc(as_of or datetime.now(UTC))
        active_signals = [signal for signal in signals if signal.timestamp <= snapshot]
        total_impact = sum(self.decayed_impact(signal, snapshot) for signal in active_signals)
        score = _clamp(self.max_score - total_impact, self.min_score, self.max_score)
        active_risk = _clamp(total_impact, 0.0, self.max_score)
        return ScorePoint(
            timestamp=snapshot,
            score=round(score, 2),
            active_risk=round(active_risk, 2),
            signal_count=len(active_signals),
        )

    def timeline(
        self,
        signals: Sequence[RiskSignal],
        start: datetime,
        end: datetime,
        step_days: int = 1,
    ) -> list[ScorePoint]:
        if step_days <= 0:
            raise ValueError("step_days must be > 0")

        start_utc = _to_utc(start)
        end_utc = _to_utc(end)
        if end_utc < start_utc:
            raise ValueError("end must be >= start")

        points: list[ScorePoint] = []
        cursor = start_utc
        ordered_signals = sorted(signals, key=lambda signal: signal.timestamp)
        step = timedelta(days=step_days)

        while cursor <= end_utc:
            points.append(self.point_at(ordered_signals, as_of=cursor))
            cursor = cursor + step

        return points

    def apply_stock_price_penalty(
        self,
        base_score: float,
        price_change_percent: float
    ) -> float:
        """
        Stosuje penalty/bonus do scoringu na podstawie zmiany ceny akcji
        
        Args:
            base_score: Bieżący scoring (0-100)
            price_change_percent: Zmiana ceny w % (np. -2.5 lub +3.0)
        
        Returns:
            Zmodyfikowany score (clamped do 0-100)
        
        Logika:
        - Każdy 1% spadku ceny = -0.5 punktu do scoringu
        - Każdy 1% wzrostu ceny = +0.5 punktu do scoringu
        
        Przykłady:
        - base_score=50, cena spadła 4% → 50 - (4 * 0.5) = 48
        - base_score=50, cena wzrosła 2% → 50 + (2 * 0.5) = 51
        """
        # Jeśli cena nie uległa zmianie
        if price_change_percent == 0:
            return base_score
        
        # Aplikuj penalty/bonus: 0.5 punktu na 1% zmiany
        adjustment = price_change_percent * 0.5
        
        # Nowy score
        new_score = base_score + adjustment
        
        # Clamp do zakresu [min_score, max_score]
        return _clamp(new_score, self.min_score, self.max_score)


def signal_from_analysis(
    analysis: Mapping[str, Any],
    timestamp: datetime,
    source_weight: float = 1.0,
    article_id: int | None = None,
) -> RiskSignal:
    return RiskSignal(
        timestamp=timestamp,
        risk_score=_to_float(analysis.get("risk_score"), 0.0),
        confidence=_to_float(analysis.get("confidence"), 0.7),
        sentiment=str(analysis.get("sentiment", "negative")).lower(),
        source_weight=source_weight,
        article_id=article_id,
        metadata={
            "risk_level": str(analysis.get("risk_level", "")),
            "summary": str(analysis.get("summary", "")),
        },
    )


def reputation_level(score: float) -> str:
    value = _clamp(score, 0.0, 100.0)
    if value < 20.0:
        return "critical"
    if value < 45.0:
        return "high"
    if value < 75.0:
        return "medium"
    return "low"


def _to_float(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


__all__ = [
    "RiskSignal",
    "ScorePoint",
    "ReputationScorer",
    "signal_from_analysis",
    "reputation_level",
]
