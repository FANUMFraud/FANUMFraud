import math
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel, Field

from analyzer import ArticleAnalyzer, ArticleInput, ArticleRiskAnalysis
from anomaly_detector import ScoreAnomalyDetector, ScoreObservation
from scorer import ReputationScorer, RiskSignal, reputation_level

app = FastAPI(title="FANUMFraud")
article_analyzer = ArticleAnalyzer()


class ScoreSignalRequest(BaseModel):
    timestamp: datetime
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    sentiment: str = "negative"
    source_weight: float = Field(default=1.0, ge=0.1, le=3.0)
    article_id: int | None = None


class ScoreRequest(BaseModel):
    signals: list[ScoreSignalRequest]
    as_of: datetime | None = None
    half_life_days: float = Field(default=45.0, gt=0)


class ScoreResponse(BaseModel):
    score: float
    level: str
    active_risk: float
    signal_count: int


class AnomalyPointRequest(BaseModel):
    timestamp: datetime
    score: float = Field(ge=0.0, le=100.0)
    article_id: int | None = None


class AnomalyRequest(BaseModel):
    observations: list[AnomalyPointRequest]
    window_size: int = Field(default=14, gt=0)
    min_history: int = Field(default=6, gt=1)
    z_threshold: float = Field(default=3.5, gt=0)
    min_abs_jump: float = Field(default=8.0, gt=0)


class AnomalyResponse(BaseModel):
    timestamp: datetime
    previous_timestamp: datetime
    previous_score: float
    current_score: float
    delta: float
    robust_z: float
    direction: str
    severity: str
    article_id: int | None = None

@app.get("/")
def root():
    return {"status": "ok", "message": "FANUMFraud działa"}


@app.post("/algorithm/analyze", response_model=ArticleRiskAnalysis)
def analyze_article(article: ArticleInput):
    return article_analyzer.analyze(article)


@app.post("/algorithm/score", response_model=ScoreResponse)
def score_company(payload: ScoreRequest):
    scorer = ReputationScorer(half_life_days=payload.half_life_days)
    signals = [
        RiskSignal(
            timestamp=item.timestamp,
            risk_score=item.risk_score,
            confidence=item.confidence,
            sentiment=item.sentiment,
            source_weight=item.source_weight,
            article_id=item.article_id,
        )
        for item in payload.signals
    ]
    point = scorer.point_at(signals, as_of=payload.as_of)

    return ScoreResponse(
        score=point.score,
        level=reputation_level(point.score),
        active_risk=point.active_risk,
        signal_count=point.signal_count,
    )


@app.post("/algorithm/anomaly", response_model=list[AnomalyResponse])
def detect_anomaly(payload: AnomalyRequest):
    detector = ScoreAnomalyDetector(
        window_size=payload.window_size,
        min_history=payload.min_history,
        z_threshold=payload.z_threshold,
        min_abs_jump=payload.min_abs_jump,
    )
    observations = [
        ScoreObservation(timestamp=item.timestamp, score=item.score, article_id=item.article_id)
        for item in payload.observations
    ]
    anomalies = detector.detect(observations)

    return [
        AnomalyResponse(
            timestamp=item.timestamp,
            previous_timestamp=item.previous_timestamp,
            previous_score=item.previous_score,
            current_score=item.current_score,
            delta=item.delta,
            robust_z=_safe_robust_z(item.robust_z),
            direction=item.direction,
            severity=item.severity,
            article_id=item.article_id,
        )
        for item in anomalies
    ]


def _safe_robust_z(value: float) -> float:
    if math.isinf(value):
        return 999.0 if value > 0 else -999.0
    return round(value, 3)
