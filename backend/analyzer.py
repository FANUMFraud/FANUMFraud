from __future__ import annotations

"""
=============================================================================
DETERMINISTIC RISK SCORING ALGORITHM FOR AML/REPUTATIONAL ANALYSIS
=============================================================================

PHILOSOPHY:
-----------
Nie ufamy "magicznym" LLM scoringom. Zamiast tego:
1. LLM wyekstrahuje STRUKTURĘ (eventy, słowa kluczowe, role, pewność)
2. Backend oblicza risk score deterministycznie z audytowalnych wag

ARCHITEKTURA SCORINGU:
----------------------
raw_score = 
    adjusted_core_points 
    + sentiment_adjustment 
    + text_context_adjustment 
    + lexical_backstop_bonus

Gdzie:
  adjusted_core_points = (keyword_points + event_points) 
                         × role_context_factor 
                         × certainty_context_factor
                         
  sentiment_adjustment = SENTIMENT_SCORE_ADJUSTMENTS[sentiment]
  
  text_context_adjustment = 
      confirmed_hits × 2.4 
      + investigated_hits × 0.8 
      - uncertainty_hits × 1.8 
      - denial_hits × 2.8 
      - positive_hits × 2.4

KAŻDA WAGA MA UZASADNIENIE:
-----------------------------
1. CATEGORY_SCORE_WEIGHTS: Jaki typ ryzyka jest najpoważniejszy?
   → AML/Sanctions > Corruption > Fraud > Legal > Governance

2. CERTAINTY_SCORE_FACTORS: Jak pewna jest sprawa?
   → Confirmed > Investigated > Alleged > Rumor > Denied
   
3. ROLE_CONTEXT_FACTORS: Jaka rola ma moja firma?
   → Accused (1.1x) > Regulator (0.98x) > Witness (0.95x) > Victim (0.62x)

4. SENTIMENT_SCORE_ADJUSTMENTS: Jaki jest ton artykułu?
   → Negative (+6.5) > Mixed (+2.5) > Neutral (0) > Positive (-5.5)

WAGI SĄ KALIBROWANE NA:
-----------------------
- Podatki regulacyjne (OFAC, KNF, UOKiK)
- Praktyki AML w Polsce i UE
- Oceny ryzyka firm finansowych
- Doświadczenie zespołu z compliance

TESTOWANIE:
-----------
Każdy zmiana musi być testowana na demo data, aby:
1. Szoki wyraźnie podnoszą scoring (np. 100 → 30)
2. Recovery jest eksponencjalny z half-life ~45 dni
3. Wagi są spójne ze wskaźnikami reputacyjnymi

DISCLAIMER:
-----------
To jest demonet system. W produkcji rekomendujemy:
- Kalibrację na historycznych danych
- Feedback loop z analitykami
- Regular audit wag
=============================================================================
"""

import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency during tests
    OpenAI = None  # type: ignore[assignment]

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "analyze_article.txt"
)
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1"
DETERMINISTIC_ALGORITHM_VERSION = "deterministic-risk-v2.1"
ANALYZER_PARSER_VERSION = "article-risk-v2.1"


class SentimentLabel(str, Enum):
    negative = "negative"
    neutral = "neutral"
    positive = "positive"
    mixed = "mixed"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CompanyRole(str, Enum):
    accused = "accused"
    victim = "victim"
    regulator = "regulator"
    witness = "witness"
    mentioned = "mentioned"
    unknown = "unknown"


class EventCategory(str, Enum):
    corruption = "corruption"
    sanctions = "sanctions"
    money_laundering = "money_laundering"
    fraud = "fraud"
    embezzlement = "embezzlement"
    legal = "legal"
    regulatory = "regulatory"
    governance = "governance"
    other = "other"


class EventCertainty(str, Enum):
    confirmed = "confirmed"
    investigated = "investigated"
    alleged = "alleged"
    rumor = "rumor"
    denied = "denied"


class RiskKeyword(BaseModel):
    keyword: str
    category: str = "general"
    mentions: int = 1
    weight: float = 1.0

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("mentions", mode="before")
    @classmethod
    def _validate_mentions(cls, value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 1
        return max(1, parsed)

    @field_validator("weight", mode="before")
    @classmethod
    def _validate_weight(cls, value: Any) -> float:
        parsed = _to_float(value, default=1.0)
        return _clamp(parsed, 0.0, 5.0)


class CompanyMention(BaseModel):
    name: str
    normalized_name: str | None = None
    role: CompanyRole = CompanyRole.mentioned
    primary: bool = False

    model_config = ConfigDict(str_strip_whitespace=True)


class RiskEvent(BaseModel):
    category: EventCategory = EventCategory.other
    title: str = ""
    description: str = ""
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    certainty: EventCertainty = EventCertainty.alleged
    companies: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    denial_date: datetime | None = None  # When company denied the allegations

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("companies", mode="before")
    @classmethod
    def _normalize_companies(cls, value: Any) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("evidence", mode="before")
    @classmethod
    def _normalize_evidence(cls, value: Any) -> list[str]:
        snippets = _normalize_string_list(value)
        return [snippet[:240] for snippet in snippets]


class ArticleInput(BaseModel):
    title: str = ""
    content: str = ""
    source: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    candidate_companies: list[str] = Field(default_factory=list)
    language_hint: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ArticleRiskAnalysis(BaseModel):
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_level: RiskLevel = RiskLevel.low
    sentiment: SentimentLabel = SentimentLabel.neutral
    confidence: float = Field(default=0.4, ge=0.0, le=1.0)
    summary: str = ""
    risk_keywords: list[RiskKeyword] = Field(default_factory=list)
    companies_mentioned: list[CompanyMention] = Field(default_factory=list)
    events: list[RiskEvent] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    algorithm_version: str = DETERMINISTIC_ALGORITHM_VERSION
    model_name: str = ""
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parser_version: str = ANALYZER_PARSER_VERSION

    @model_validator(mode="after")
    def _post_process(self) -> "ArticleRiskAnalysis":
        self.risk_score = round(_clamp(self.risk_score, 0.0, 100.0), 2)
        self.confidence = round(_clamp(self.confidence, 0.0, 1.0), 3)
        self.risk_level = risk_level_from_score(self.risk_score)
        self.risk_keywords = self.risk_keywords[:8]
        self.events = self.events[:5]
        self.score_breakdown = _round_nested_numbers(self.score_breakdown)
        if not self.summary:
            self.summary = _default_summary(self.risk_score, self.sentiment)
        return self


class ArticleAnalyzer:
    """Analyze one article into a normalized risk JSON structure."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENROUTER_URL,
        prompt_path: Path | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1200,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt_path = prompt_path or DEFAULT_PROMPT_PATH
        self.prompt_template = self._load_prompt(self.prompt_path)

        resolved_key = (
            api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        )
        if client is not None:
            self.client = client
        elif OpenAI is not None and resolved_key:
            self.client = OpenAI(api_key=resolved_key, base_url=base_url)
        else:
            self.client = None

    def analyze(self, article: ArticleInput | Mapping[str, Any]) -> ArticleRiskAnalysis:
        payload = (
            article
            if isinstance(article, ArticleInput)
            else ArticleInput.model_validate(article)
        )
        if not payload.title and not payload.content:
            return ArticleRiskAnalysis(
                risk_score=0.0,
                sentiment=SentimentLabel.neutral,
                confidence=0.2,
                summary="No content to analyze.",
                model_name="empty-input",
            )

        if self.client is None:
            return self._heuristic_analysis(payload, model_name="heuristic-no-llm")

        try:
            raw_output = self._call_llm(payload)
            llm_payload = parse_analysis_payload(raw_output)
            normalized = self._normalize_llm_payload(llm_payload, payload)
            analysis = ArticleRiskAnalysis.model_validate(normalized)
            analysis.model_name = self.model
            return analysis
        except Exception:
            return self._heuristic_analysis(
                payload, model_name=f"heuristic-fallback:{self.model}"
            )

    def analyze_batch(
        self, articles: Sequence[ArticleInput | Mapping[str, Any]]
    ) -> list[ArticleRiskAnalysis]:
        return [self.analyze(article) for article in articles]

    def _call_llm(self, article: ArticleInput) -> str:
        article_json = json.dumps(
            article.model_dump(mode="json", exclude_none=True), ensure_ascii=False
        )
        user_prompt = (
            "Analyze the following ARTICLE_JSON and return only one JSON object matching the schema.\n"
            f"ARTICLE_JSON:\n{article_json}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": self.prompt_template},
                {"role": "user", "content": user_prompt},
            ],
        )

        if not response.choices:
            raise RuntimeError("LLM returned no choices.")

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("LLM returned empty content.")
        return content

    def _normalize_llm_payload(
        self, payload: Mapping[str, Any], article: ArticleInput
    ) -> dict[str, Any]:
        risk_keywords = self._normalize_keywords(
            payload.get("risk_keywords") or payload.get("keywords") or []
        )[:8]
        events = self._normalize_events(
            payload.get("events") or payload.get("risk_events") or []
        )[:5]
        article_text = f"{article.title}\n{article.content}".strip()
        companies = self._normalize_companies(
            payload.get("companies_mentioned") or payload.get("companies") or [],
            article.candidate_companies,
            article_text=article_text,
        )

        sentiment_value = _first_present_value(
            payload, "sentiment", "sentiment_label", "overall_sentiment"
        )
        normalized_sentiment = _normalize_sentiment(sentiment_value)

        legacy_model_score = _to_float(
            _first_present_value(
                payload, "risk_score", "overall_risk_score", "score", "risk"
            ),
            default=-1.0,
        )
        risk_score, breakdown = _deterministic_risk_score(
            article_text=article_text,
            risk_keywords=risk_keywords,
            events=events,
            companies=companies,
            sentiment=normalized_sentiment,
        )

        if legacy_model_score >= 0:
            breakdown["legacy_model_score"] = round(
                _clamp(legacy_model_score, 0.0, 100.0), 2
            )
            breakdown["legacy_model_score_used"] = False

        confidence = _deterministic_confidence(
            article_text=article_text,
            risk_keywords=risk_keywords,
            events=events,
            companies=companies,
        )

        summary = str(
            payload.get("summary") or payload.get("description") or ""
        ).strip()
        if not summary:
            summary = _build_structured_summary(
                risk_score=risk_score,
                sentiment=normalized_sentiment,
                breakdown=breakdown,
            )

        normalized: dict[str, Any] = {
            "risk_score": _clamp(risk_score, 0.0, 100.0),
            "sentiment": normalized_sentiment,
            "confidence": confidence,
            "summary": summary,
            "risk_keywords": risk_keywords,
            "companies_mentioned": companies,
            "events": events,
            "score_breakdown": breakdown,
            "algorithm_version": DETERMINISTIC_ALGORITHM_VERSION,
            "parser_version": ANALYZER_PARSER_VERSION,
        }
        return normalized

    def _normalize_keywords(self, value: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if isinstance(value, Mapping):
            for category, keywords in value.items():
                if isinstance(keywords, str):
                    normalized.append(
                        {
                            "keyword": keywords,
                            "category": str(category),
                            "mentions": 1,
                            "weight": 1.0,
                        }
                    )
                elif isinstance(keywords, Sequence):
                    for keyword in keywords:
                        as_text = str(keyword).strip()
                        if as_text:
                            normalized.append(
                                {
                                    "keyword": as_text,
                                    "category": str(category),
                                    "mentions": 1,
                                    "weight": 1.0,
                                }
                            )
            return normalized

        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return normalized

        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    normalized.append(
                        {
                            "keyword": text,
                            "category": "general",
                            "mentions": 1,
                            "weight": 1.0,
                        }
                    )
                continue

            if isinstance(item, Mapping):
                keyword = str(item.get("keyword") or item.get("term") or "").strip()
                if not keyword:
                    continue
                normalized.append(
                    {
                        "keyword": keyword,
                        "category": str(item.get("category") or "general").strip(),
                        "mentions": item.get("mentions", 1),
                        "weight": item.get("weight", 1.0),
                    }
                )

        return normalized

    def _normalize_companies(
        self,
        value: Any,
        candidates: Sequence[str],
        article_text: str,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()

        items: list[Any]
        if isinstance(value, Mapping):
            items = [value]
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            items = list(value)
        elif isinstance(value, str):
            items = [value]
        else:
            items = []

        for item in items:
            if isinstance(item, str):
                company_name = item.strip()
                if not company_name:
                    continue
                normalized_name = _normalize_company_name(company_name)
                if normalized_name in seen:
                    continue
                seen.add(normalized_name)
                normalized.append(
                    {
                        "name": company_name,
                        "normalized_name": normalized_name,
                        "role": CompanyRole.mentioned.value,
                        "primary": False,
                    }
                )
                continue

            if isinstance(item, Mapping):
                company_name = str(
                    item.get("name") or item.get("company") or ""
                ).strip()
                if not company_name:
                    continue
                normalized_name = str(
                    item.get("normalized_name") or _normalize_company_name(company_name)
                ).strip()
                if normalized_name in seen:
                    continue
                seen.add(normalized_name)
                normalized.append(
                    {
                        "name": company_name,
                        "normalized_name": normalized_name,
                        "role": _normalize_company_role(item.get("role")),
                        "primary": bool(item.get("primary", False)),
                    }
                )

        lowered_text = _to_ascii_lower(article_text)
        for candidate in candidates:
            candidate_name = candidate.strip()
            if not candidate_name:
                continue
            normalized_name = _normalize_company_name(candidate_name)
            if normalized_name in seen:
                continue
            if _to_ascii_lower(candidate_name) not in lowered_text:
                continue
            seen.add(normalized_name)
            normalized.append(
                {
                    "name": candidate_name,
                    "normalized_name": normalized_name,
                    "role": CompanyRole.mentioned.value,
                    "primary": False,
                }
            )

        if normalized and not any(item["primary"] for item in normalized):
            normalized[0]["primary"] = True

        return normalized

    def _normalize_events(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return []

        normalized: list[dict[str, Any]] = []
        for event in value:
            if isinstance(event, str):
                text = event.strip()
                if text:
                    normalized.append(
                        {
                            "category": EventCategory.other.value,
                            "title": text,
                            "description": text,
                            "severity": 0.3,
                            "certainty": EventCertainty.alleged.value,
                            "companies": [],
                            "evidence": [],
                        }
                    )
                continue

            if not isinstance(event, Mapping):
                continue

            normalized.append(
                {
                    "category": _normalize_event_category(event.get("category")),
                    "title": str(event.get("title") or event.get("name") or "").strip(),
                    "description": str(
                        event.get("description") or event.get("details") or ""
                    ).strip(),
                    "severity": _to_float(event.get("severity"), default=0.3),
                    "certainty": _normalize_event_certainty(event.get("certainty")),
                    "companies": event.get("companies") or event.get("targets") or [],
                    "evidence": event.get("evidence") or event.get("quotes") or [],
                }
            )

        return normalized

    def _heuristic_analysis(
        self, article: ArticleInput, model_name: str
    ) -> ArticleRiskAnalysis:
        text_original = f"{article.title}\n{article.content}".strip()
        lowered = _to_ascii_lower(text_original)

        category_hits: dict[str, float] = {}
        keyword_rows: list[dict[str, Any]] = []
        event_rows: list[dict[str, Any]] = []

        for category, config in RISK_TERM_CONFIG.items():
            terms = config["terms"]
            weight = float(config["weight"])
            mentions = 0
            first_term = ""
            first_pattern: str | None = None

            for term_config in terms:
                keyword, pattern = _resolve_keyword_pattern(term_config)
                if not keyword or not pattern:
                    continue

                count = _count_pattern(lowered, pattern)
                if count <= 0:
                    continue
                mentions += count
                if not first_term:
                    first_term = keyword
                    first_pattern = pattern
                keyword_rows.append(
                    {
                        "keyword": keyword,
                        "category": category,
                        "mentions": count,
                        "weight": round(weight, 3),
                    }
                )

            if mentions <= 0:
                continue

            category_hits[category] = mentions * weight
            event_rows.append(
                {
                    "category": category,
                    "title": f"{category.replace('_', ' ').title()} signal",
                    "description": f"Detected {mentions} mentions related to {category.replace('_', ' ')}.",
                    "severity": _clamp((mentions * weight) / 4.0, 0.15, 1.0),
                    "certainty": _detect_certainty(lowered),
                    "companies": _detect_companies(
                        lowered, article.candidate_companies
                    ),
                    "evidence": [
                        _extract_evidence_snippet(
                            text_original, first_term, first_pattern
                        )
                    ]
                    if first_term
                    else [],
                }
            )

        positive_mentions = sum(
            _count_pattern(lowered, pattern) for pattern in POSITIVE_PATTERNS
        )

        companies = [
            {
                "name": company,
                "normalized_name": _normalize_company_name(company),
                "role": CompanyRole.mentioned.value,
                "primary": False,
            }
            for company in _detect_companies(lowered, article.candidate_companies)
        ]
        if companies:
            companies[0]["primary"] = True

        if not keyword_rows and article.candidate_companies:
            companies = [
                {
                    "name": article.candidate_companies[0],
                    "normalized_name": _normalize_company_name(
                        article.candidate_companies[0]
                    ),
                    "role": CompanyRole.mentioned.value,
                    "primary": True,
                }
            ]

        uncertainty_present = _contains_any_pattern(lowered, UNCERTAINTY_PATTERNS)
        sentiment_seed = _heuristic_seed_sentiment(
            has_risk_hits=bool(category_hits),
            positive_mentions=positive_mentions,
            uncertainty_present=uncertainty_present,
        )
        risk_score, breakdown = _deterministic_risk_score(
            article_text=text_original,
            risk_keywords=keyword_rows,
            events=event_rows,
            companies=companies,
            sentiment=sentiment_seed,
        )

        sentiment = _heuristic_sentiment(risk_score, positive_mentions)
        if sentiment != sentiment_seed:
            risk_score, breakdown = _deterministic_risk_score(
                article_text=text_original,
                risk_keywords=keyword_rows,
                events=event_rows,
                companies=companies,
                sentiment=sentiment,
            )

        confidence = _deterministic_confidence(
            article_text=text_original,
            risk_keywords=keyword_rows,
            events=event_rows,
            companies=companies,
        )

        summary = _build_heuristic_summary(risk_score, sentiment, category_hits)

        return ArticleRiskAnalysis(
            risk_score=risk_score,
            sentiment=sentiment,
            confidence=confidence,
            summary=summary,
            risk_keywords=keyword_rows,
            companies_mentioned=companies,
            events=event_rows,
            score_breakdown=breakdown,
            algorithm_version=DETERMINISTIC_ALGORITHM_VERSION,
            parser_version=ANALYZER_PARSER_VERSION,
            model_name=model_name,
        )

    @staticmethod
    def _load_prompt(path: Path) -> str:
        return path.read_text(encoding="utf-8").strip()


def analyze_article(
    article: ArticleInput | Mapping[str, Any], analyzer: ArticleAnalyzer | None = None
) -> ArticleRiskAnalysis:
    active_analyzer = analyzer or ArticleAnalyzer()
    return active_analyzer.analyze(article)


def parse_analysis_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Model output is empty.")

    fenced_match = re.search(
        r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    direct = _try_parse_json(cleaned)
    if direct is not None:
        return direct

    extracted = _extract_first_json_object(cleaned)
    if extracted is not None:
        return extracted

    raise ValueError("Could not parse JSON object from model output.")


def risk_level_from_score(score: float) -> RiskLevel:
    value = _clamp(score, 0.0, 100.0)
    if value >= 75.0:
        return RiskLevel.critical
    if value >= 45.0:
        return RiskLevel.high
    if value >= 20.0:
        return RiskLevel.medium
    return RiskLevel.low


def _default_summary(risk_score: float, sentiment: SentimentLabel) -> str:
    if risk_score < 20.0:
        return "Low-risk article signal."
    if risk_score < 45.0:
        return "Moderate risk signal detected."
    if risk_score < 75.0:
        return "High risk signal detected and should be reviewed."
    if sentiment == SentimentLabel.negative:
        return "Critical negative risk signal detected."
    return "Critical risk signal detected."


def _deterministic_risk_score(
    article_text: str,
    risk_keywords: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    companies: Sequence[Mapping[str, Any]],
    sentiment: str,
) -> tuple[float, dict[str, Any]]:
    normalized_text = _to_ascii_lower(article_text)
    sentiment_label = _normalize_sentiment(sentiment)
    role_lookup = _build_role_lookup(companies)
    primary_role = _primary_role(companies)

    keyword_points_by_category: dict[str, float] = {}
    for item in risk_keywords:
        category = _normalize_event_category(item.get("category"))
        mentions = _clamp(_to_float(item.get("mentions"), 1.0), 1.0, 6.0)
        weight = _clamp(_to_float(item.get("weight"), 1.0), 0.2, 3.0)
        category_weight = CATEGORY_SCORE_WEIGHTS.get(
            category, CATEGORY_SCORE_WEIGHTS[EventCategory.other.value]
        )
        points = (
            min(mentions, 4.0) * weight * category_weight * KEYWORD_POINT_MULTIPLIER
        )
        keyword_points_by_category[category] = (
            keyword_points_by_category.get(category, 0.0) + points
        )

    lexical_backstop_points = _lexical_backstop_points(normalized_text)
    for category, points in lexical_backstop_points.items():
        existing = keyword_points_by_category.get(category, 0.0)
        keyword_points_by_category[category] = max(existing, points)

    lexical_backstop_total = sum(lexical_backstop_points.values())
    lexical_backstop_category_count = len(lexical_backstop_points)

    event_points_by_category: dict[str, float] = {}
    certainty_factors: list[float] = []
    for item in events:
        category = _normalize_event_category(item.get("category"))
        severity = _clamp(_to_float(item.get("severity"), 0.3), 0.0, 1.0)
        certainty = _normalize_event_certainty(item.get("certainty"))
        certainty_factor = CERTAINTY_SCORE_FACTORS.get(
            certainty, CERTAINTY_SCORE_FACTORS[EventCertainty.alleged.value]
        )
        certainty_factors.append(certainty_factor)

        category_weight = CATEGORY_SCORE_WEIGHTS.get(
            category, CATEGORY_SCORE_WEIGHTS[EventCategory.other.value]
        )
        evidence = _normalize_string_list(item.get("evidence"))
        evidence_factor = 1.0 + (min(len(evidence), 4) * 0.06)
        role_factor = _event_role_factor(item.get("companies"), role_lookup)

        event_points = (
            (EVENT_BASE_POINTS + (severity * EVENT_SEVERITY_POINTS))
            * category_weight
            * certainty_factor
            * evidence_factor
            * role_factor
        )
        event_points = _clamp(event_points, 0.0, EVENT_MAX_POINTS)
        event_points_by_category[category] = (
            event_points_by_category.get(category, 0.0) + event_points
        )

    total_keyword_points = sum(keyword_points_by_category.values())
    total_event_points = sum(event_points_by_category.values())
    core_points = total_keyword_points + total_event_points

    role_context_factor = ROLE_CONTEXT_FACTORS.get(
        primary_role, ROLE_CONTEXT_FACTORS[CompanyRole.mentioned.value]
    )
    certainty_context_factor = 1.0
    if certainty_factors:
        avg_certainty = sum(certainty_factors) / len(certainty_factors)
        certainty_context_factor = _clamp(0.78 + (avg_certainty * 0.34), 0.72, 1.2)

    positive_hits = sum(
        _count_pattern(normalized_text, pattern) for pattern in POSITIVE_PATTERNS
    )
    uncertainty_hits = sum(
        _count_pattern(normalized_text, pattern) for pattern in UNCERTAINTY_PATTERNS
    )
    denial_hits = sum(
        _count_pattern(normalized_text, pattern) for pattern in DENIAL_PATTERNS
    )
    confirmed_hits = sum(
        _count_pattern(normalized_text, pattern) for pattern in CONFIRMED_PATTERNS
    )
    investigated_hits = sum(
        _count_pattern(normalized_text, pattern) for pattern in INVESTIGATED_PATTERNS
    )

    sentiment_adjustment = SENTIMENT_SCORE_ADJUSTMENTS.get(
        sentiment_label, SENTIMENT_SCORE_ADJUSTMENTS[SentimentLabel.neutral.value]
    )
    if core_points <= 0:
        sentiment_adjustment = min(sentiment_adjustment, 0.0)

    text_context_adjustment = (
        (confirmed_hits * 2.4)
        + (investigated_hits * 0.8)
        - (uncertainty_hits * 1.8)
        - (denial_hits * 2.8)
        - (positive_hits * 2.4)
    )
    text_context_adjustment = _clamp(text_context_adjustment, -18.0, 12.0)

    lexical_backstop_bonus = 0.0
    if not risk_keywords and not events and lexical_backstop_category_count >= 2:
        lexical_backstop_bonus = LEXICAL_GAP_BONUS_BASE + min(
            lexical_backstop_total * LEXICAL_GAP_BONUS_SCALE,
            LEXICAL_GAP_BONUS_CAP,
        )

    adjusted_core = core_points * role_context_factor * certainty_context_factor
    raw_score = (
        adjusted_core
        + sentiment_adjustment
        + text_context_adjustment
        + lexical_backstop_bonus
    )
    if adjusted_core < 10.0 and (positive_hits > 0 or denial_hits > 0):
        raw_score -= 4.0

    final_score = _clamp(raw_score, 0.0, 100.0)
    category_totals = _merge_category_points(
        keyword_points_by_category, event_points_by_category
    )
    breakdown: dict[str, Any] = {
        "version": DETERMINISTIC_ALGORITHM_VERSION,
        "core_points": core_points,
        "keyword_points": total_keyword_points,
        "event_points": total_event_points,
        "role_context_factor": role_context_factor,
        "certainty_context_factor": certainty_context_factor,
        "sentiment_adjustment": sentiment_adjustment,
        "text_context_adjustment": text_context_adjustment,
        "lexical_backstop_bonus": lexical_backstop_bonus,
        "raw_score": raw_score,
        "final_score": final_score,
        "top_categories": _category_points_view(category_totals),
        "keyword_category_points": _category_points_view(keyword_points_by_category),
        "lexical_backstop_points": _category_points_view(lexical_backstop_points),
        "event_category_points": _category_points_view(event_points_by_category),
        "text_hits": {
            "positive": positive_hits,
            "uncertainty": uncertainty_hits,
            "denial": denial_hits,
            "confirmed": confirmed_hits,
            "investigated": investigated_hits,
        },
        "company_context": {
            "primary_role": primary_role,
            "companies_count": len(companies),
        },
    }
    return final_score, _round_nested_numbers(breakdown)


def _deterministic_confidence(
    article_text: str,
    risk_keywords: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    companies: Sequence[Mapping[str, Any]],
) -> float:
    normalized_text = _to_ascii_lower(article_text)
    uncertainty_hits = sum(
        _count_pattern(normalized_text, pattern) for pattern in UNCERTAINTY_PATTERNS
    )
    evidence_count = 0
    confirmed_or_investigated = 0
    weak_certainty = 0

    for item in events:
        evidence_count += len(_normalize_string_list(item.get("evidence")))
        certainty = _normalize_event_certainty(item.get("certainty"))
        if certainty in {
            EventCertainty.confirmed.value,
            EventCertainty.investigated.value,
        }:
            confirmed_or_investigated += 1
        if certainty in {EventCertainty.rumor.value, EventCertainty.denied.value}:
            weak_certainty += 1

    has_primary_company = any(
        bool(item.get("primary")) for item in companies if isinstance(item, Mapping)
    )

    base = 0.22
    base += min(len(risk_keywords), 8) * 0.03
    base += min(len(events), 5) * 0.09
    base += min(evidence_count, 6) * 0.025
    base += min(confirmed_or_investigated, 3) * 0.05
    base -= min(weak_certainty, 3) * 0.04
    base -= min(uncertainty_hits, 4) * 0.015

    text_length = len(article_text.strip())
    if text_length >= 800:
        base += 0.06
    elif text_length >= 300:
        base += 0.03

    if has_primary_company:
        base += 0.04

    return _clamp(base, 0.2, 0.95)


def _build_structured_summary(
    risk_score: float,
    sentiment: str,
    breakdown: Mapping[str, Any],
) -> str:
    top_categories = breakdown.get("top_categories")
    strongest_category = ""
    if isinstance(top_categories, Sequence) and top_categories:
        first = top_categories[0]
        if isinstance(first, Mapping):
            strongest_category = str(first.get("category") or "").strip()

    category_label = strongest_category.replace("_", " ").strip()
    sentiment_label = _normalize_sentiment(sentiment)

    if risk_score < 20.0:
        return "Low-risk signal based on limited adverse evidence in the article."
    if risk_score < 45.0:
        if category_label:
            return f"Moderate {category_label} signal detected with mixed evidence strength."
        return "Moderate risk signal detected with mixed evidence strength."
    if risk_score < 75.0:
        if category_label:
            return f"High {category_label} risk signal detected and should be reviewed."
        return "High risk signal detected and should be reviewed."
    if sentiment_label == SentimentLabel.negative.value and category_label:
        return f"Critical negative {category_label} risk signal with strong supporting indicators."
    if sentiment_label == SentimentLabel.negative.value:
        return "Critical negative risk signal with strong supporting indicators."
    return "Critical risk signal detected with strong supporting indicators."


def _build_role_lookup(companies: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for company in companies:
        role = _normalize_company_role(company.get("role"))
        names = [company.get("name"), company.get("normalized_name")]
        for value in names:
            if value is None:
                continue
            normalized_name = _normalize_company_name(str(value))
            if normalized_name:
                lookup[normalized_name] = role
    return lookup


def _primary_role(companies: Sequence[Mapping[str, Any]]) -> str:
    for company in companies:
        if not bool(company.get("primary")):
            continue
        return _normalize_company_role(company.get("role"))

    strongest_role = CompanyRole.mentioned.value
    strongest_factor = ROLE_CONTEXT_FACTORS[strongest_role]
    for company in companies:
        role = _normalize_company_role(company.get("role"))
        factor = ROLE_CONTEXT_FACTORS.get(
            role, ROLE_CONTEXT_FACTORS[CompanyRole.mentioned.value]
        )
        if factor > strongest_factor:
            strongest_role = role
            strongest_factor = factor
    return strongest_role


def _event_role_factor(companies: Any, role_lookup: Mapping[str, str]) -> float:
    names = _normalize_string_list(companies)
    if not names:
        return 1.0

    factors: list[float] = []
    for name in names:
        normalized_name = _normalize_company_name(name)
        if not normalized_name:
            continue
        role = role_lookup.get(normalized_name)
        if role is None:
            continue
        factors.append(
            ROLE_EVENT_FACTORS.get(
                role, ROLE_EVENT_FACTORS[CompanyRole.mentioned.value]
            )
        )

    if not factors:
        return 1.0
    return max(factors)


def _lexical_backstop_points(normalized_text: str) -> dict[str, float]:
    points_by_category: dict[str, float] = {}
    for category, config in RISK_TERM_CONFIG.items():
        mentions = 0
        for term_config in config.get("terms", []):
            _, pattern = _resolve_keyword_pattern(term_config)
            if not pattern:
                continue
            mentions += _count_pattern(normalized_text, pattern)
        if mentions <= 0:
            continue

        weight = _clamp(_to_float(config.get("weight"), 1.0), 0.6, 1.8)
        points = min(float(mentions), 4.0) * weight * LEXICAL_BACKSTOP_MULTIPLIER
        points_by_category[category] = round(points, 3)
    return points_by_category


def _merge_category_points(*maps: Mapping[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for mapping in maps:
        for category, points in mapping.items():
            merged[category] = merged.get(category, 0.0) + float(points)
    return merged


def _category_points_view(
    points_by_category: Mapping[str, float],
) -> list[dict[str, Any]]:
    rows = [
        {"category": category, "points": round(points, 2)}
        for category, points in sorted(
            points_by_category.items(), key=lambda item: item[1], reverse=True
        )
        if points > 0
    ]
    return rows[:4]


def _heuristic_seed_sentiment(
    has_risk_hits: bool,
    positive_mentions: int,
    uncertainty_present: bool,
) -> SentimentLabel:
    if has_risk_hits and positive_mentions > 0:
        return SentimentLabel.mixed
    if has_risk_hits and uncertainty_present:
        return SentimentLabel.mixed
    if has_risk_hits:
        return SentimentLabel.negative
    if positive_mentions >= 2:
        return SentimentLabel.positive
    return SentimentLabel.neutral


def _round_nested_numbers(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 3)
    if isinstance(value, Mapping):
        return {str(key): _round_nested_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_nested_numbers(item) for item in value]
    return value


def _try_parse_json(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    while start != -1:
        fragment = _balanced_fragment(text, start)
        if fragment:
            parsed = _try_parse_json(fragment)
            if parsed is not None:
                return parsed
        start = text.find("{", start + 1)
    return None


def _balanced_fragment(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
            continue

    return None


def _build_heuristic_summary(
    risk_score: float,
    sentiment: SentimentLabel,
    category_hits: Mapping[str, float],
) -> str:
    if not category_hits:
        return "No significant AML or reputational risk indicators were detected in the article."

    strongest_category = max(category_hits.items(), key=lambda item: item[1])[0]
    if risk_score >= 75.0:
        return f"Critical {strongest_category.replace('_', ' ')} risk signal detected with strong negative context."
    if risk_score >= 45.0:
        return f"High {strongest_category.replace('_', ' ')} risk signal detected and requires review."
    if sentiment == SentimentLabel.mixed:
        return f"Mixed sentiment with moderate {strongest_category.replace('_', ' ')} risk indicators."
    return f"Low-to-moderate {strongest_category.replace('_', ' ')} risk indicators detected."


def _heuristic_sentiment(risk_score: float, positive_mentions: int) -> SentimentLabel:
    if risk_score >= 55.0:
        return SentimentLabel.negative
    if risk_score >= 22.0:
        return SentimentLabel.mixed
    if positive_mentions >= 2:
        return SentimentLabel.positive
    return SentimentLabel.neutral


def _count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


def _contains_any_pattern(text: str, patterns: Sequence[str]) -> bool:
    return any(_count_pattern(text, pattern) > 0 for pattern in patterns)


def _detect_certainty(lowered_text: str) -> EventCertainty:
    if _contains_any_pattern(lowered_text, CONFIRMED_PATTERNS):
        return EventCertainty.confirmed
    if _contains_any_pattern(lowered_text, INVESTIGATED_PATTERNS):
        return EventCertainty.investigated
    if _contains_any_pattern(lowered_text, DENIAL_PATTERNS):
        return EventCertainty.denied
    if _contains_any_pattern(lowered_text, UNCERTAINTY_PATTERNS):
        return EventCertainty.rumor
    return EventCertainty.alleged


def _extract_evidence_snippet(
    text: str, term: str, pattern: str | None = None, radius: int = 80
) -> str:
    if not text or not term:
        return ""

    if pattern:
        normalized_text = _to_ascii_lower(text)
        match = re.search(pattern, normalized_text)
        if match is not None:
            start = max(0, match.start() - radius)
            end = min(len(text), match.end() + radius)
            snippet = text[start:end]
            return re.sub(r"\s+", " ", snippet).strip()

    lowered = text.lower()
    index = lowered.find(term.lower())
    if index < 0:
        index = _to_ascii_lower(text).find(_to_ascii_lower(term))
        if index < 0:
            return ""

    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    snippet = text[start:end]
    return re.sub(r"\s+", " ", snippet).strip()


def _detect_companies(lowered_text: str, candidates: Sequence[str]) -> list[str]:
    normalized_text = _to_ascii_lower(lowered_text)
    detected: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        if _to_ascii_lower(normalized) in normalized_text:
            detected.append(normalized)
    return detected


def _resolve_keyword_pattern(term_config: Any) -> tuple[str, str]:
    if isinstance(term_config, str):
        keyword = term_config.strip()
        return keyword, _pattern_for_term(keyword)

    if isinstance(term_config, Mapping):
        keyword = str(
            term_config.get("keyword") or term_config.get("term") or ""
        ).strip()
        explicit_pattern = term_config.get("pattern")
        if explicit_pattern:
            return keyword, _to_ascii_lower(str(explicit_pattern).strip())
        return keyword, _pattern_for_term(keyword)

    return "", ""


def _pattern_for_term(term: str) -> str:
    normalized = _to_ascii_lower(term).strip()
    if not normalized:
        return ""
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return ""
    if len(tokens) == 1:
        return rf"\b{re.escape(tokens[0])}\w*\b"
    inflected_parts = [rf"{re.escape(token)}\w*" for token in tokens]
    return rf"\b{'\\s+'.join(inflected_parts)}\b"


def _first_present_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _normalize_sentiment(value: Any) -> str:
    label = _normalize_label(value)
    if not label:
        return SentimentLabel.neutral.value
    if label in SENTIMENT_ALIASES:
        return SENTIMENT_ALIASES[label]
    if "negat" in label or "negative" in label:
        return SentimentLabel.negative.value
    if "pozy" in label or "positive" in label:
        return SentimentLabel.positive.value
    if "mix" in label or "mieszan" in label or "ambivalent" in label:
        return SentimentLabel.mixed.value
    return SentimentLabel.neutral.value


def _normalize_company_role(value: Any) -> str:
    label = _normalize_label(value)
    if not label:
        return CompanyRole.mentioned.value
    if label in COMPANY_ROLE_ALIASES:
        return COMPANY_ROLE_ALIASES[label]
    if any(term in label for term in ["oskar", "accus", "charged", "suspect"]):
        return CompanyRole.accused.value
    if any(term in label for term in ["victim", "pokrzywd", "poszkod"]):
        return CompanyRole.victim.value
    if any(
        term in label
        for term in ["regulator", "urzad", "prokuratur", "watchdog", "authority"]
    ):
        return CompanyRole.regulator.value
    if any(term in label for term in ["witness", "swiadk"]):
        return CompanyRole.witness.value
    if any(term in label for term in ["unknown", "nieznan"]):
        return CompanyRole.unknown.value
    return CompanyRole.mentioned.value


def _normalize_event_category(value: Any) -> str:
    label = _normalize_label(value)
    if not label:
        return EventCategory.other.value
    if label in EVENT_CATEGORY_ALIASES:
        return EVENT_CATEGORY_ALIASES[label]
    if any(
        term in label
        for term in ["money laundering", "aml", "pran", "terror financing"]
    ):
        return EventCategory.money_laundering.value
    if any(term in label for term in ["corrupt", "bribe", "lapow", "kickback"]):
        return EventCategory.corruption.value
    if any(term in label for term in ["sanction", "embargo", "ofac", "sankcj"]):
        return EventCategory.sanctions.value
    if any(term in label for term in ["fraud", "oszust", "wylud", "scam", "ponzi"]):
        return EventCategory.fraud.value
    if any(term in label for term in ["embezz", "malwers", "defraud", "sprzeniew"]):
        return EventCategory.embezzlement.value
    if any(
        term in label
        for term in ["legal", "zarzut", "oskarz", "prokuratur", "lawsuit", "court"]
    ):
        return EventCategory.legal.value
    if any(
        term in label for term in ["regulator", "uokik", "knf", "compliance", "policy"]
    ):
        return EventCategory.regulatory.value
    if any(
        term in label for term in ["govern", "board", "zarzad", "ceo", "management"]
    ):
        return EventCategory.governance.value
    return EventCategory.other.value


def _normalize_event_certainty(value: Any) -> str:
    label = _normalize_label(value)
    if not label:
        return EventCertainty.alleged.value
    if label in EVENT_CERTAINTY_ALIASES:
        return EVENT_CERTAINTY_ALIASES[label]
    if any(
        term in label
        for term in ["confirmed", "convicted", "proven", "potwierdz", "udowodn"]
    ):
        return EventCertainty.confirmed.value
    if any(
        term in label
        for term in ["investigat", "inquiry", "sledzt", "postepow", "probe"]
    ):
        return EventCertainty.investigated.value
    if any(term in label for term in ["deni", "zaprzecz", "refut", "dismiss"]):
        return EventCertainty.denied.value
    if any(term in label for term in ["rumor", "niepotwier", "rzekom", "speculat"]):
        return EventCertainty.rumor.value
    return EventCertainty.alleged.value


def _normalize_label(value: Any) -> str:
    if value is None:
        return ""
    text = _to_ascii_lower(str(value))
    text = re.sub(r"[/\\\-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_company_name(name: str) -> str:
    cleaned = _to_ascii_lower(name)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s\.\-&]", "", cleaned)
    return cleaned


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, str)):
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized
    return []


def _to_ascii_lower(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_float(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return default
        try:
            return float(match.group(0))
        except ValueError:
            return default
    return default


RISK_TERM_CONFIG: dict[str, dict[str, Any]] = {
    "corruption": {
        "weight": 1.35,
        "terms": [
            {"keyword": "lapowka", "pattern": r"\blapowk\w*\b"},
            {"keyword": "korupcja", "pattern": r"\bkorupcj\w*\b"},
            {"keyword": "corruption", "pattern": r"\bcorrupt\w*\b"},
            {"keyword": "bribe", "pattern": r"\bbrib\w*\b"},
            {"keyword": "kickback", "pattern": r"\bkickback\w*\b"},
        ],
    },
    "sanctions": {
        "weight": 1.4,
        "terms": [
            {"keyword": "sankcje", "pattern": r"\bsankcj\w*\b"},
            {"keyword": "sanction", "pattern": r"\bsanction\w*\b"},
            {"keyword": "ofac", "pattern": r"\bofac\b"},
            {"keyword": "embargo", "pattern": r"\bembargo\w*\b"},
        ],
    },
    "money_laundering": {
        "weight": 1.55,
        "terms": [
            {"keyword": "pranie pieniedzy", "pattern": r"\bpran\w*\s+pieniedz\w*\b"},
            {"keyword": "money laundering", "pattern": r"\bmoney\s+launder\w*\b"},
            {"keyword": "aml", "pattern": r"\baml\b"},
            {"keyword": "terrorist financing", "pattern": r"\bfinanc\w*\s+terror\w*\b"},
        ],
    },
    "fraud": {
        "weight": 1.25,
        "terms": [
            {"keyword": "oszustwo", "pattern": r"\boszust\w*\b"},
            {"keyword": "fraud", "pattern": r"\bfraud\w*\b"},
            {"keyword": "wyludzenie", "pattern": r"\bwyludz\w*\b"},
            {"keyword": "scam", "pattern": r"\bscam\w*\b"},
            {"keyword": "ponzi", "pattern": r"\bponzi\w*\b"},
        ],
    },
    "embezzlement": {
        "weight": 1.2,
        "terms": [
            {"keyword": "defraudacja", "pattern": r"\bdefraud\w*\b"},
            {"keyword": "malwersacja", "pattern": r"\bmalwers\w*\b"},
            {"keyword": "embezzlement", "pattern": r"\bembezz\w*\b"},
            {"keyword": "sprzeniewierzenie", "pattern": r"\bsprzeniew\w*\b"},
        ],
    },
    "legal": {
        "weight": 1.15,
        "terms": [
            {"keyword": "zarzuty", "pattern": r"\bzarzut\w*\b"},
            {"keyword": "akt oskarzenia", "pattern": r"\boskarzen\w*\b"},
            {"keyword": "prokuratura", "pattern": r"\bprokuratur\w*\b"},
            {"keyword": "areszt", "pattern": r"\bareszt\w*\b"},
            {"keyword": "investigation", "pattern": r"\binvestigat\w*\b"},
            {"keyword": "lawsuit", "pattern": r"\blawsuit\w*\b"},
        ],
    },
    "regulatory": {
        "weight": 1.05,
        "terms": [
            {"keyword": "knf", "pattern": r"\bknf\b"},
            {"keyword": "uokik", "pattern": r"\buokik\b"},
            {
                "keyword": "kara administracyjna",
                "pattern": r"\bkara\w*\s+administracyjn\w*\b",
            },
            {"keyword": "regulator", "pattern": r"\bregulator\w*\b"},
            {"keyword": "compliance breach", "pattern": r"\bcompliance\s+breach\w*\b"},
        ],
    },
    "governance": {
        "weight": 1.0,
        "terms": [
            {"keyword": "zarzad", "pattern": r"\bzarzad\w*\b"},
            {"keyword": "board", "pattern": r"\bboard\w*\b"},
            {"keyword": "ceo resigned", "pattern": r"\bceo\s+resign\w*\b"},
            {
                "keyword": "conflict of interest",
                "pattern": r"\bconflict\s+of\s+interest\w*\b",
            },
        ],
    },
}

POSITIVE_PATTERNS = [
    r"\buniewinn\w*\b",
    r"\boddalon\w*\s+zarzut\w*\b",
    r"\bbrak\s+nieprawidlow\w*\b",
    r"\bpozytywn\w*\s+ocen\w*\b",
    r"\bcompliance\s+award\w*\b",
    r"\bwzorow\w*\s+zgodn\w*\b",
]

UNCERTAINTY_PATTERNS = [
    r"\brzekom\w*\b",
    r"\bdomnieman\w*\b",
    r"\balleg\w*\b",
    r"\brumou?r\w*\b",
    r"\bniepotwierdz\w*\b",
    r"\bnie\s+potwierdz\w*\b",
]

DENIAL_PATTERNS = [
    r"\bzaprzecz\w*\b",
    r"\bdeni\w*\b",
    r"\boddalil\w*\s+zarzut\w*\b",
    r"\brefut\w*\b",
]

INVESTIGATED_PATTERNS = [
    r"\bsledztw\w*\b",
    r"\bpostepowan\w*\b",
    r"\binvestigat\w*\b",
    r"\bprobe\w*\b",
    r"\binquiry\w*\b",
]

CONFIRMED_PATTERNS = [
    r"\bskazan\w*\b",
    r"\bprawomocn\w*\s+wyrok\w*\b",
    r"\bconvict\w*\b",
    r"\bguilty\s+verdict\w*\b",
    r"\bconfirmed\w*\b",
]

SENTIMENT_ALIASES = {
    "negative": SentimentLabel.negative.value,
    "negatywny": SentimentLabel.negative.value,
    "negatywna": SentimentLabel.negative.value,
    "negatywne": SentimentLabel.negative.value,
    "neutral": SentimentLabel.neutral.value,
    "neutralny": SentimentLabel.neutral.value,
    "neutralna": SentimentLabel.neutral.value,
    "positive": SentimentLabel.positive.value,
    "pozytywny": SentimentLabel.positive.value,
    "pozytywna": SentimentLabel.positive.value,
    "mixed": SentimentLabel.mixed.value,
    "mieszany": SentimentLabel.mixed.value,
    "mieszana": SentimentLabel.mixed.value,
}

COMPANY_ROLE_ALIASES = {
    "accused": CompanyRole.accused.value,
    "oskarzony": CompanyRole.accused.value,
    "oskarzona": CompanyRole.accused.value,
    "suspect": CompanyRole.accused.value,
    "defendant": CompanyRole.accused.value,
    "victim": CompanyRole.victim.value,
    "ofiara": CompanyRole.victim.value,
    "pokrzywdzony": CompanyRole.victim.value,
    "poszkodowany": CompanyRole.victim.value,
    "regulator": CompanyRole.regulator.value,
    "authority": CompanyRole.regulator.value,
    "witness": CompanyRole.witness.value,
    "swiadek": CompanyRole.witness.value,
    "mentioned": CompanyRole.mentioned.value,
    "mention": CompanyRole.mentioned.value,
    "wspomniany": CompanyRole.mentioned.value,
    "unknown": CompanyRole.unknown.value,
    "nieznany": CompanyRole.unknown.value,
}

EVENT_CATEGORY_ALIASES = {
    "corruption": EventCategory.corruption.value,
    "korupcja": EventCategory.corruption.value,
    "bribery": EventCategory.corruption.value,
    "sankcje": EventCategory.sanctions.value,
    "sanctions": EventCategory.sanctions.value,
    "money laundering": EventCategory.money_laundering.value,
    "pranie pieniedzy": EventCategory.money_laundering.value,
    "aml": EventCategory.money_laundering.value,
    "fraud": EventCategory.fraud.value,
    "oszustwo": EventCategory.fraud.value,
    "embezzlement": EventCategory.embezzlement.value,
    "defraudacja": EventCategory.embezzlement.value,
    "legal": EventCategory.legal.value,
    "regulatory": EventCategory.regulatory.value,
    "governance": EventCategory.governance.value,
}

EVENT_CERTAINTY_ALIASES = {
    "confirmed": EventCertainty.confirmed.value,
    "potwierdzone": EventCertainty.confirmed.value,
    "investigated": EventCertainty.investigated.value,
    "w trakcie sledztwa": EventCertainty.investigated.value,
    "alleged": EventCertainty.alleged.value,
    "zarzuty": EventCertainty.alleged.value,
    "rumor": EventCertainty.rumor.value,
    "niepotwierdzone": EventCertainty.rumor.value,
    "denied": EventCertainty.denied.value,
    "zaprzeczone": EventCertainty.denied.value,
}

# ============================================================================
# DETERMINISTIC SCORING CONSTANTS & DOCUMENTATION
# ============================================================================
#
# Każda stała ma uzasadnienie biznesowe i calibrowanie na praktyce AML/compliance
#

KEYWORD_POINT_MULTIPLIER = 2.2
# Mnożnik dla słów kluczowych. 2.2 to umiarkowany wpływ - zapewnia że słowa
# się liczą, ale nie dominują nad eventami (EVENT_BASE_POINTS=4.5).

LEXICAL_BACKSTOP_MULTIPLIER = 3.2
# Mnożnik gdy brak struktury od LLM ale mamy słowa kluczowe.
# 3.2 > 2.2 bo fallback musi być bardziej agresywny.

LEXICAL_GAP_BONUS_BASE = 12.0
LEXICAL_GAP_BONUS_SCALE = 0.45
LEXICAL_GAP_BONUS_CAP = 10.0
# Bonus gdy brak keywords/events ale wielekategorie (np. "money_laundering" + "sanctions")
# BASE=12.0 solidny bonus, SCALE=0.45 per kategoria, CAP=10.0 max

EVENT_BASE_POINTS = 4.5
EVENT_SEVERITY_POINTS = 15.0
# Event = 4.5 + (severity × 15.0) × kategoria_weight × certainty_factor
# Razem event może wnieść 4.5-19.5 punktów base

EVENT_MAX_POINTS = 34.0
# Cap na event (po multiplikatorach): zapobiega dominacji jednej sprawy

CATEGORY_SCORE_WEIGHTS = {
    # AML - compliance risk dla KNF/OFAC/UOKiK - NAJPOWAŻNIEJSZE
    EventCategory.money_laundering.value: 1.5,
    # Sankcje - międzynarodowe kary, blokada aktywów - BARDZO POWAŻNE
    EventCategory.sanctions.value: 1.4,
    # Korupcja - legal + reputacyjne - POWAŻNE
    EventCategory.corruption.value: 1.32,
    # Oszustwa - zwykle vs klienci - UMIARKOWANE
    EventCategory.fraud.value: 1.2,
    # Defraudacja - wewnętrzne - UMIARKOWANE
    EventCategory.embezzlement.value: 1.15,
    # Postępowania prawne - mogą być sznurem - PONIŻEJ 1.0
    EventCategory.legal.value: 0.98,
    # Sprawy regulacyjne - częste, rutynowe - NISKIE
    EventCategory.regulatory.value: 0.9,
    # Sprawy governance - market ocenił - NAJNISKIE
    EventCategory.governance.value: 0.82,
    # Inne - fallback - BARDZO NISKIE
    EventCategory.other.value: 0.6,
}

CERTAINTY_SCORE_FACTORS = {
    # Confirmed: wyroki, zawiadomienia - TO JEST FAKT
    EventCertainty.confirmed.value: 1.22,
    # Investigated: prokuratura, regulator - FORMALNE
    EventCertainty.investigated.value: 1.0,
    # Alleged: zarzuty, ankiety - ZNACZNY RABAT
    EventCertainty.alleged.value: 0.7,
    # Rumor: pogłoski, anonimowe - POWAŻNY RABAT
    EventCertainty.rumor.value: 0.44,
    # Denied: zaprzeczenia, oddalono - NIEMAL IGNORUJEMY
    EventCertainty.denied.value: 0.16,
}

ROLE_EVENT_FACTORS = {
    # Oskarżona: wysoki multiplier dla eventu
    CompanyRole.accused.value: 1.15,
    # Regulator: baseline
    CompanyRole.regulator.value: 1.0,
    # Świadek: lekki rabat
    CompanyRole.witness.value: 0.96,
    # Wspomniany: peryferyjny rabat
    CompanyRole.mentioned.value: 0.92,
    # Nieznany: największy rabat
    CompanyRole.unknown.value: 0.86,
    # Ofiara: SIGNIFICANT rabat - bycie ofiarą nie jest ryzykiem
    CompanyRole.victim.value: 0.65,
}

ROLE_CONTEXT_FACTORS = {
    # Główna firma oskarżona: 10% premium
    CompanyRole.accused.value: 1.1,
    # Główna firma regulator: lekki rabat
    CompanyRole.regulator.value: 0.98,
    # Główna firma świadek: rabat
    CompanyRole.witness.value: 0.95,
    # Główna firma wspomniany: rabat
    CompanyRole.mentioned.value: 0.9,
    # Główna firma nieznany: rabat
    CompanyRole.unknown.value: 0.86,
    # Główna firma ofiara: poważny rabat
    CompanyRole.victim.value: 0.62,
}

SENTIMENT_SCORE_ADJUSTMENTS = {
    # Negatywny: artykuł wzmacnia ryzyko
    SentimentLabel.negative.value: 6.5,
    # Mieszany: zarówno złe i dobre
    SentimentLabel.mixed.value: 2.5,
    # Neutralny: bez wpływu
    SentimentLabel.neutral.value: 0.0,
    # Pozytywny: artykuł mityguje ryzyko
    SentimentLabel.positive.value: -5.5,
}



__all__ = [
    "DETERMINISTIC_ALGORITHM_VERSION",
    "ANALYZER_PARSER_VERSION",
    "ArticleAnalyzer",
    "ArticleInput",
    "ArticleRiskAnalysis",
    "RiskKeyword",
    "RiskEvent",
    "CompanyMention",
    "analyze_article",
    "parse_analysis_payload",
    "risk_level_from_score",
]
