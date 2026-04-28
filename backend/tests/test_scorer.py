from datetime import UTC, datetime, timedelta

from scorer import ReputationScorer, RiskSignal


def test_score_is_100_without_signals() -> None:
    scorer = ReputationScorer(half_life_days=30)
    result = scorer.score_at([])
    assert result == 100.0


def test_decay_halves_impact_after_half_life() -> None:
    scorer = ReputationScorer(half_life_days=10)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    signal = RiskSignal(timestamp=start, risk_score=80, confidence=1.0, sentiment="negative")

    initial_score = scorer.score_at([signal], as_of=start)
    score_after_half_life = scorer.score_at([signal], as_of=start + timedelta(days=10))

    assert round(initial_score, 2) == 20.0
    assert round(score_after_half_life, 2) == 60.0


def test_positive_signal_cannot_push_above_100() -> None:
    scorer = ReputationScorer(half_life_days=20)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    signal = RiskSignal(timestamp=now, risk_score=70, confidence=1.0, sentiment="positive")

    score = scorer.score_at([signal], as_of=now)
    assert score == 100.0


def test_timeline_recovers_over_time_without_new_events() -> None:
    scorer = ReputationScorer(half_life_days=12)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    signal = RiskSignal(timestamp=start, risk_score=60, confidence=0.9, sentiment="negative")

    timeline = scorer.timeline([signal], start=start, end=start + timedelta(days=24), step_days=12)
    values = [point.score for point in timeline]

    assert len(values) == 3
    assert values[0] < values[1] < values[2]


def test_future_signals_do_not_affect_historical_snapshot() -> None:
    scorer = ReputationScorer(half_life_days=20)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    past_signal = RiskSignal(timestamp=start, risk_score=50, confidence=1.0, sentiment="negative")
    future_signal = RiskSignal(
        timestamp=start + timedelta(days=10),
        risk_score=90,
        confidence=1.0,
        sentiment="negative",
    )

    historical = scorer.point_at([past_signal, future_signal], as_of=start)
    baseline = scorer.point_at([past_signal], as_of=start)
    future_view = scorer.point_at([past_signal, future_signal], as_of=start + timedelta(days=10))

    assert historical.score == baseline.score
    assert historical.signal_count == 1
    assert future_view.signal_count == 2


def test_source_weight_changes_signal_impact() -> None:
    scorer = ReputationScorer(half_life_days=20)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    low_credibility = RiskSignal(
        timestamp=now,
        risk_score=50,
        confidence=1.0,
        sentiment="negative",
        source_weight=0.7,
    )
    official_source = RiskSignal(
        timestamp=now,
        risk_score=50,
        confidence=1.0,
        sentiment="negative",
        source_weight=1.35,
    )

    low_score = scorer.score_at([low_credibility], as_of=now)
    official_score = scorer.score_at([official_source], as_of=now)

    assert official_score < low_score
