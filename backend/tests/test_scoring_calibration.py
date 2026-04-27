import json
from pathlib import Path

import pytest

from analyzer import (
    DETERMINISTIC_ALGORITHM_VERSION,
    ArticleAnalyzer,
    ArticleInput,
)


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **_: object) -> object:
        message = type("Message", (), {"content": self._content})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def _load_cases() -> list[dict[str, object]]:
    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "article_calibration_cases.json"
    )
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


CASES = _load_cases()


def _analyze(article: dict[str, str], payload: dict[str, object]):
    analyzer = ArticleAnalyzer(
        client=_FakeClient(json.dumps(payload, ensure_ascii=False)), model="fake-model"
    )
    return analyzer.analyze(
        ArticleInput(title=article.get("title", ""), content=article.get("content", ""))
    )


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_calibration_ranges_for_reference_cases(case: dict[str, object]) -> None:
    article = case["article"]
    payload = case["payload"]
    assert isinstance(article, dict)
    assert isinstance(payload, dict)

    analysis = _analyze(article, payload)
    score = analysis.risk_score

    expected_min = float(case["expected_min"])
    expected_max = float(case["expected_max"])

    assert expected_min <= score <= expected_max
    assert analysis.algorithm_version == DETERMINISTIC_ALGORITHM_VERSION
    assert (
        round(float(analysis.score_breakdown["final_score"]), 2) == analysis.risk_score
    )


def test_certainty_order_is_monotonic_for_same_event() -> None:
    def _score_for(certainty: str) -> float:
        payload = {
            "sentiment": "negative",
            "confidence": 0.8,
            "summary": "",
            "risk_keywords": [
                {
                    "keyword": "fraud",
                    "category": "fraud",
                    "mentions": 2,
                    "weight": 1.0,
                }
            ],
            "companies_mentioned": [
                {
                    "name": "Acme SA",
                    "normalized_name": "acme sa",
                    "role": "accused",
                    "primary": True,
                }
            ],
            "events": [
                {
                    "category": "fraud",
                    "title": "Fraud signal",
                    "description": "Structured test event",
                    "severity": 0.8,
                    "certainty": certainty,
                    "companies": ["Acme SA"],
                    "evidence": ["single source"],
                }
            ],
        }
        analysis = _analyze(
            article={
                "title": "Quarterly update",
                "content": "Neutral corporate update.",
            },
            payload=payload,
        )
        return analysis.risk_score

    confirmed = _score_for("confirmed")
    investigated = _score_for("investigated")
    alleged = _score_for("alleged")
    rumor = _score_for("rumor")
    denied = _score_for("denied")

    assert confirmed > investigated > alleged > rumor > denied


def test_role_order_is_monotonic_for_same_event() -> None:
    def _score_for(role: str) -> float:
        payload = {
            "sentiment": "negative",
            "confidence": 0.8,
            "summary": "",
            "risk_keywords": [
                {
                    "keyword": "sanctions",
                    "category": "sanctions",
                    "mentions": 1,
                    "weight": 1.0,
                }
            ],
            "companies_mentioned": [
                {
                    "name": "Acme SA",
                    "normalized_name": "acme sa",
                    "role": role,
                    "primary": True,
                }
            ],
            "events": [
                {
                    "category": "sanctions",
                    "title": "Sanctions signal",
                    "description": "Structured test event",
                    "severity": 0.7,
                    "certainty": "investigated",
                    "companies": ["Acme SA"],
                    "evidence": ["single source"],
                }
            ],
        }
        analysis = _analyze(
            article={
                "title": "Quarterly update",
                "content": "Neutral corporate update.",
            },
            payload=payload,
        )
        return analysis.risk_score

    accused = _score_for("accused")
    mentioned = _score_for("mentioned")
    victim = _score_for("victim")

    assert accused > mentioned > victim


def test_category_weighting_prefers_aml_categories() -> None:
    def _score_for(category: str) -> float:
        payload = {
            "sentiment": "negative",
            "confidence": 0.8,
            "summary": "",
            "risk_keywords": [
                {
                    "keyword": category,
                    "category": category,
                    "mentions": 1,
                    "weight": 1.0,
                }
            ],
            "companies_mentioned": [
                {
                    "name": "Acme SA",
                    "normalized_name": "acme sa",
                    "role": "accused",
                    "primary": True,
                }
            ],
            "events": [
                {
                    "category": category,
                    "title": "Category signal",
                    "description": "Structured test event",
                    "severity": 0.7,
                    "certainty": "investigated",
                    "companies": ["Acme SA"],
                    "evidence": ["single source"],
                }
            ],
        }
        analysis = _analyze(
            article={
                "title": "Quarterly update",
                "content": "Neutral corporate update.",
            },
            payload=payload,
        )
        return analysis.risk_score

    money_laundering = _score_for("money_laundering")
    sanctions = _score_for("sanctions")
    governance = _score_for("governance")

    assert money_laundering > sanctions > governance
