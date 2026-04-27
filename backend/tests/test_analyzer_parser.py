import json

from analyzer import (
    ANALYZER_PARSER_VERSION,
    DETERMINISTIC_ALGORITHM_VERSION,
    ArticleAnalyzer,
    ArticleInput,
    parse_analysis_payload,
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


def test_parse_analysis_payload_from_fenced_json() -> None:
    raw = """
```json
{
  "risk_score": 64,
  "sentiment": "negative",
  "confidence": 0.81,
  "summary": "Formal allegations are described.",
  "risk_keywords": [],
  "companies_mentioned": [],
  "events": []
}
```
"""
    parsed = parse_analysis_payload(raw)

    assert parsed["risk_score"] == 64
    assert parsed["sentiment"] == "negative"


def test_parse_analysis_payload_from_noisy_text() -> None:
    raw = 'Model answer: {"risk_score": 10, "sentiment": "neutral", "confidence": 0.4} End'
    parsed = parse_analysis_payload(raw)

    assert parsed["risk_score"] == 10
    assert parsed["sentiment"] == "neutral"


def test_analyzer_heuristic_detects_risk_keywords() -> None:
    analyzer = ArticleAnalyzer(api_key=None)
    article = ArticleInput(
        title="Spolka pod lupa prokuratury",
        content=(
            "Prokuratura postawila zarzuty zarzadowi spolki. "
            "W artykule padaja slowa korupcja, lapowka i pranie pieniedzy."
        ),
        candidate_companies=["Przyklad SA"],
    )

    analysis = analyzer.analyze(article)

    assert analysis.risk_score >= 45
    assert analysis.sentiment in {"negative", "mixed"}
    assert analysis.risk_keywords
    assert analysis.model_name.startswith("heuristic")


def test_zero_risk_score_from_llm_is_preserved() -> None:
    llm_payload = {
        "risk_score": 0,
        "sentiment": "neutral",
        "confidence": 0.91,
        "summary": "No risk signal.",
        "risk_keywords": [],
        "companies_mentioned": [],
        "events": [],
    }
    analyzer = ArticleAnalyzer(
        client=_FakeClient(json.dumps(llm_payload)), model="fake-model"
    )

    analysis = analyzer.analyze(
        ArticleInput(title="Neutral release", content="No allegations reported.")
    )

    assert analysis.risk_score == 0.0
    assert analysis.model_name == "fake-model"


def test_llm_risk_score_is_not_used_directly() -> None:
    llm_payload = {
        "risk_score": 98,
        "sentiment": "neutral",
        "confidence": 0.99,
        "summary": "No confirmed risk signal.",
        "risk_keywords": [],
        "companies_mentioned": [
            {"name": "Acme SA", "role": "mentioned", "primary": True}
        ],
        "events": [],
    }
    analyzer = ArticleAnalyzer(
        client=_FakeClient(json.dumps(llm_payload)), model="fake-model"
    )

    analysis = analyzer.analyze(
        ArticleInput(
            title="Neutral release",
            content="Company reported stable operations and no allegations.",
        )
    )

    assert analysis.risk_score <= 5.0
    assert analysis.score_breakdown.get("legacy_model_score") == 98.0
    assert analysis.score_breakdown.get("legacy_model_score_used") is False


def test_analysis_contains_breakdown_and_algorithm_version() -> None:
    analyzer = ArticleAnalyzer(api_key=None)
    article = ArticleInput(
        title="Prokuratura bada mozliwe oszustwo",
        content="Media opisuja zarzuty, sledztwo i podejrzenie prania pieniedzy.",
        candidate_companies=["Przyklad SA"],
    )

    analysis = analyzer.analyze(article)

    assert analysis.algorithm_version == DETERMINISTIC_ALGORITHM_VERSION
    assert analysis.parser_version == ANALYZER_PARSER_VERSION
    assert analysis.score_breakdown["version"] == DETERMINISTIC_ALGORITHM_VERSION
    assert (
        round(float(analysis.score_breakdown["final_score"]), 2) == analysis.risk_score
    )


def test_llm_extraction_gaps_are_backstopped_by_text_signals() -> None:
    llm_payload = {
        "sentiment": "neutral",
        "confidence": 0.9,
        "summary": "No material risk in extraction.",
        "risk_keywords": [],
        "companies_mentioned": [],
        "events": [],
    }
    analyzer = ArticleAnalyzer(
        client=_FakeClient(json.dumps(llm_payload)), model="fake-model"
    )

    analysis = analyzer.analyze(
        ArticleInput(
            title="Doniesienia o korupcji",
            content="Media opisuja korupcje, lapowki i mozliwe pranie pieniedzy.",
        )
    )

    assert analysis.risk_score >= 20.0
    assert analysis.score_breakdown["lexical_backstop_points"]


def test_llm_labels_are_normalized_without_fallback() -> None:
    llm_payload = {
        "risk_score": 33,
        "sentiment": "negatywny",
        "confidence": 0.8,
        "summary": "Investigation references.",
        "risk_keywords": [{"keyword": "korupcja", "mentions": 1, "weight": 1.0}],
        "companies_mentioned": [
            {"name": "Acme SA", "role": "oskarzona", "primary": True}
        ],
        "events": [
            {
                "category": "money laundering",
                "title": "Probe",
                "description": "Authorities are investigating.",
                "severity": 0.6,
                "certainty": "under investigation",
            }
        ],
    }
    analyzer = ArticleAnalyzer(
        client=_FakeClient(json.dumps(llm_payload)), model="fake-model"
    )

    analysis = analyzer.analyze(
        ArticleInput(title="Notice", content="Regulator update.")
    )

    assert analysis.sentiment == "negative"
    assert analysis.companies_mentioned[0].role == "accused"
    assert analysis.events[0].category == "money_laundering"
    assert analysis.events[0].certainty == "investigated"
    assert analysis.model_name == "fake-model"


def test_heuristic_handles_inflected_polish_forms() -> None:
    analyzer = ArticleAnalyzer(api_key=None)
    article = ArticleInput(
        title="Korupcyjny proceder w spolce",
        content="Media opisuja lapowki, oszustwach i proby wyludzen. Trwa sledztwo.",
    )

    analysis = analyzer.analyze(article)
    keywords = {keyword.keyword for keyword in analysis.risk_keywords}

    assert "lapowka" in keywords
    assert "oszustwo" in keywords
