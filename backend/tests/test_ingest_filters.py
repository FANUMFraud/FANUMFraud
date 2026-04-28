from pipeline.ingest import contains_risk_keywords, contains_watchlist_mentions


def test_contains_risk_keywords_uses_extended_patterns():
    text = "Prokuratura wszczęła postępowanie ws. możliwego oszustwa finansowego."
    assert contains_risk_keywords(text)


def test_contains_watchlist_mentions_detects_requested_entities():
    title = "UOKiK bada działania ORLEN"
    content = "W komunikacie wskazano także na potencjalne naruszenia rynku."
    assert contains_watchlist_mentions(title, content)


def test_contains_watchlist_mentions_handles_polish_characters():
    assert contains_watchlist_mentions("Żabka komentuje wyniki", "Brak ryzyk")
