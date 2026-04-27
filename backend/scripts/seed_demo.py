from __future__ import annotations

import argparse
import dataclasses
import json
import math
import random
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import SessionLocal, engine, init_db
from models import Article, Company, ScoreHistory
from scorer import ReputationScorer, RiskSignal

DEMO_URL_PREFIX = "https://demo.fanumfraud.local/articles"
DEFAULT_ARTICLES_PER_COMPANY = 150
DEFAULT_RANDOM_SEED = 20260427
SOURCE_NAMES = [
    "money.pl",
    "bankier.pl",
    "businessinsider.com.pl",
    "pb.pl",
    "parkiet.com",
    "rp.pl",
    "demo-press.local",
]


@dataclass(frozen=True)
class DemoCompany:
    name: str
    nip: str
    aliases: list[str]
    industry: str
    ticker: str | None
    categories: list[str]
    risk_probability: float
    minor_probability: float
    risk_range: tuple[int, int]
    
    # Szoki - domyślnie None, będą losowo inicjalizowane
    has_shock: bool | None = None
    shock_day_offset: int | None = None
    shock_category: str | None = None
    shock_risk: int | None = None
    pre_shock_risk_probability: float | None = None
    post_shock_recovery_days: int = 60


@dataclass(frozen=True)
class ArticleSignal:
    category: str
    risk_score: float
    confidence: float
    sentiment: str


DEMO_COMPANIES: list[DemoCompany] = [
    DemoCompany(
        name="Baltica Energy S.A.",
        nip="1010000001",
        aliases=["Baltica Energy", "Baltica", "BE S.A."],
        industry="energy",
        ticker="BET",
        categories=["corruption", "legal", "governance"],
        risk_probability=0.035,
        minor_probability=0.08,
        risk_range=(34, 60),
    ),
    DemoCompany(
        name="Vistula Logistics Sp. z o.o.",
        nip="1010000002",
        aliases=["Vistula Logistics", "V-Logistics", "VLOG"],
        industry="transport",
        ticker=None,
        categories=["sanctions", "regulatory", "money_laundering"],
        risk_probability=0.035,
        minor_probability=0.09,
        risk_range=(30, 56),
    ),
    DemoCompany(
        name="NovaTech Solutions S.A.",
        nip="1010000003",
        aliases=["NovaTech", "NTS", "Nova Tech"],
        industry="technology",
        ticker="NTS",
        categories=["fraud", "regulatory", "governance"],
        risk_probability=0.025,
        minor_probability=0.10,
        risk_range=(20, 46),
    ),
    DemoCompany(
        name="GreenFoods Polska Sp. z o.o.",
        nip="1010000004",
        aliases=["GreenFoods", "Green Foods Polska", "GFP"],
        industry="food",
        ticker=None,
        categories=["regulatory", "other"],
        risk_probability=0.005,
        minor_probability=0.04,
        risk_range=(8, 22),
    ),
    DemoCompany(
        name="Mazovia Construction S.A.",
        nip="1010000005",
        aliases=["Mazovia Construction", "Mazovia Budownictwo", "MCON"],
        industry="construction",
        ticker="MCON",
        categories=["corruption", "fraud", "legal"],
        risk_probability=0.035,
        minor_probability=0.08,
        risk_range=(34, 60),
    ),
    DemoCompany(
        name="Amber Capital Markets S.A.",
        nip="1010000006",
        aliases=["Amber Capital", "ACM", "Amber Markets"],
        industry="finance",
        ticker="ACM",
        categories=["money_laundering", "sanctions", "regulatory"],
        risk_probability=0.035,
        minor_probability=0.09,
        risk_range=(32, 60),
    ),
    DemoCompany(
        name="Northwind Pharma Sp. z o.o.",
        nip="1010000007",
        aliases=["Northwind Pharma", "Northwind", "NWP"],
        industry="pharma",
        ticker=None,
        categories=["regulatory", "legal", "governance"],
        risk_probability=0.02,
        minor_probability=0.10,
        risk_range=(18, 46),
    ),
    DemoCompany(
        name="Solaris Components S.A.",
        nip="1010000008",
        aliases=["Solaris Components", "Solaris Parts", "SCOMP"],
        industry="manufacturing",
        ticker="SCP",
        categories=["governance", "regulatory", "fraud"],
        risk_probability=0.015,
        minor_probability=0.08,
        risk_range=(14, 38),
    ),
    DemoCompany(
        name="Quantum Retail Group S.A.",
        nip="1010000009",
        aliases=["Quantum Retail", "Q Retail", "QRG"],
        industry="retail",
        ticker="QRG",
        categories=["fraud", "legal", "regulatory"],
        risk_probability=0.025,
        minor_probability=0.09,
        risk_range=(18, 48),
    ),
    DemoCompany(
        name="Asteria Mining S.A.",
        nip="1010000010",
        aliases=["Asteria Mining", "Asteria", "AMIN"],
        industry="mining",
        ticker="AMN",
        categories=["corruption", "regulatory", "governance"],
        risk_probability=0.03,
        minor_probability=0.10,
        risk_range=(26, 54),
    ),
    DemoCompany(
        name="BalticPay S.A.",
        nip="1010000011",
        aliases=["BalticPay", "Baltic Pay", "BPAY"],
        industry="payments",
        ticker="BPY",
        categories=["money_laundering", "fraud", "regulatory"],
        risk_probability=0.035,
        minor_probability=0.08,
        risk_range=(30, 58),
    ),
    DemoCompany(
        name="HelioSoft Cloud Sp. z o.o.",
        nip="1010000012",
        aliases=["HelioSoft", "HelioSoft Cloud", "HSC"],
        industry="software",
        ticker=None,
        categories=["regulatory", "governance", "other"],
        risk_probability=0.008,
        minor_probability=0.06,
        risk_range=(8, 28),
    ),
]


def _initialize_shocks(
    companies: list[DemoCompany], 
    rng: random.Random
) -> list[DemoCompany]:
    """
    Inicjalizuj szoki dla wszystkich firm.
    
    Logika:
    - 40% firm: has_shock=False (czysta reputacja)
    - 60% firm: has_shock=True + losowy dzień + losowa kategoria
    
    Każdy seed daje INNE szoki (ZAWSZE losowe, nie deterministyczne).
    """
    initialized = []
    
    for company in companies:
        # Czy ta firma ma szok?
        has_shock = rng.random() < 0.60  # 60% szansa na szok
        
        if has_shock:
            # Szok gdzieś pośrodku timeline (dzień 120-200 z 270)
            shock_day = rng.randint(120, 200)
            
            # Losowa kategoria z dozwolonych dla tej firmy
            shock_cat = rng.choice(company.categories)
            
            # Intensywność szoku
            shock_risk_val = rng.randint(60, 75)
            
            # Przed szokiem: połowa zwykłego ryzyko
            pre_risk_prob = company.risk_probability / 2.0
        else:
            # Brak szoku: bardzo czysta reputacja
            shock_day = 999  # Never happens
            shock_cat = "other"
            shock_risk_val = 0
            pre_risk_prob = company.risk_probability * 0.05  # BARDZO mało ryzyka
        
        # Stwórz nową kopię z wartościami
        modified = dataclasses.replace(
            company,
            has_shock=has_shock,
            shock_day_offset=shock_day,
            shock_category=shock_cat,
            shock_risk=shock_risk_val,
            pre_shock_risk_probability=pre_risk_prob,
        )
        initialized.append(modified)
    
    return initialized


def main() -> None:
    args = _parse_args()
    seed_value, seed_mode = _resolve_seed(args.seed)
    rng = random.Random(seed_value)

    # ✅ Inicjalizuj szoki dla wszystkich firm
    demo_companies_initialized = _initialize_shocks(DEMO_COMPANIES, rng)

    _wait_for_database(timeout_seconds=args.db_timeout)
    init_db()
    db = SessionLocal()
    try:
        _remove_existing_demo_articles(db)
        companies = [_upsert_company(db, item) for item in demo_companies_initialized]
        db.commit()

        article_count = 0
        score_count = 0
        scorer = ReputationScorer(half_life_days=45)

        for company, config in zip(companies, demo_companies_initialized, strict=True):
            signals: list[RiskSignal] = []
            score_points: list[float] = []
            start = _utc_now() - timedelta(days=args.days)

            for index in range(args.per_company):
                published_at, current_day = _published_at(start, args.days, args.per_company, index, rng)
                signal = _article_signal(config, index, args.per_company, current_day, rng)
                title, content = _article_text(config, signal, index, published_at)

                article = Article(
                    url=f"{DEMO_URL_PREFIX}/{_slug(config.name)}/{index + 1:04d}",
                    title=title,
                    content=content,
                    source=rng.choice(SOURCE_NAMES),
                    published_at=published_at,
                    processed=True,
                )
                db.add(article)
                db.flush()
                article_count += 1

                if signal.risk_score > 0:
                    signals.append(
                        RiskSignal(
                            timestamp=published_at,
                            risk_score=signal.risk_score,
                            confidence=signal.confidence,
                            sentiment=signal.sentiment,
                            article_id=article.id,
                        )
                    )

                should_record = signal.risk_score > 0 or index % 20 == 0 or index == args.per_company - 1
                if should_record:
                    score = scorer.point_at(signals, as_of=published_at).score
                    db.add(
                        ScoreHistory(
                            company_id=company.id,
                            article_id=article.id,
                            score=score,
                            risk_score=signal.risk_score,
                            category=signal.category,
                            recorded_at=published_at,
                        )
                    )
                    score_points.append(score)
                    score_count += 1

            company.current_score = scorer.point_at(signals, as_of=_utc_now()).score
            
            # Apply minimum floor to ensure realistic scores:
            # - Clean companies (no shock): min 82.0 (very stable reputation)
            # - Shocked companies: min 8.0 (severe issues but not bottom)
            # - This prevents accumulation of multiple high-risk signals from clamping to 0.0
            if score_points:
                if config.has_shock:
                    # Shocked company: allow low scores but not zero
                    company.current_score = max(company.current_score, 8.0)
                elif config.risk_probability <= 0.02:
                    # Clean company: ensure good reputation
                    company.current_score = max(company.current_score, 82.0)

        db.commit()
        _index_companies(companies)

        print(
            json.dumps(
                {
                    "companies": len(companies),
                    "articles": article_count,
                    "score_history_points": score_count,
                    "articles_per_company": args.per_company,
                    "seed": seed_value,
                    "seed_mode": seed_mode,
                },
                ensure_ascii=False,
            )
        )
    finally:
        db.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed FANUMFraud with demo data.")
    parser.add_argument("--per-company", type=int, default=DEFAULT_ARTICLES_PER_COMPANY)
    parser.add_argument("--days", type=int, default=270)
    parser.add_argument("--db-timeout", type=int, default=90)
    parser.add_argument(
        "--seed",
        default=str(DEFAULT_RANDOM_SEED),
        help="Stable integer seed or 'random' for a new demo variant on each run.",
    )
    return parser.parse_args()


def _wait_for_database(timeout_seconds: int) -> None:
    deadline = time.monotonic() + max(timeout_seconds, 1)
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(2)

    raise RuntimeError(f"Database is not ready after {timeout_seconds}s") from last_error


def _resolve_seed(raw_seed: str) -> tuple[int, str]:
    normalized = str(raw_seed).strip().lower()
    if normalized in {"random", "rand", "auto"}:
        return random.SystemRandom().randrange(1, 2**63), "random"

    try:
        return int(normalized), "stable"
    except ValueError as exc:
        raise SystemExit("--seed must be an integer or 'random'") from exc


def _remove_existing_demo_articles(db) -> None:
    demo_article_ids = [
        row[0]
        for row in db.query(Article.id)
        .filter(Article.url.like(f"{DEMO_URL_PREFIX}/%"))
        .all()
    ]
    if not demo_article_ids:
        return

    db.query(ScoreHistory).filter(ScoreHistory.article_id.in_(demo_article_ids)).delete(synchronize_session=False)
    db.query(Article).filter(Article.id.in_(demo_article_ids)).delete(synchronize_session=False)
    db.commit()


def _upsert_company(db, config: DemoCompany) -> Company:
    company = db.query(Company).filter(Company.nip == config.nip).first()
    if company is None:
        company = Company(name=config.name, nip=config.nip)
        db.add(company)

    company.name = config.name
    company.aliases = json.dumps(config.aliases, ensure_ascii=False)
    company.industry = config.industry
    company.ticker_gpw = config.ticker
    company.current_score = 100.0
    return company


def _article_signal(config: DemoCompany, index: int, per_company: int, current_day: int, rng: random.Random) -> ArticleSignal:
    """
    Trzech-fazowa logika generacji sygnałów ryzyka:
    
    1. PRZED SZOKIEM (days_to_shock > 0):
       Niskie ryzyko z pre_shock_risk_probability
    
    2. SZOK (abs(days_to_shock) <= 3):
       Wysokie ryzyko = shock_risk (peak)
    
    3. PO SZOKU (days_to_shock < 0):
       Eksponencjalne zmniejszanie ryzyka (decay)
    
    4. BEZ SZOKU (has_shock=False):
       Bardzo czysta reputacja (prawie brak ryzyka)
    """
    
    if config.has_shock:
        days_to_shock = config.shock_day_offset - current_day
        
        # ===== SZOK! (±3 dni od shock_day_offset) =====
        if abs(days_to_shock) <= 3:
            return ArticleSignal(
                category=config.shock_category,
                risk_score=float(config.shock_risk + rng.randint(-4, 4)),
                confidence=round(rng.uniform(0.85, 0.95), 2),
                sentiment="negative",
            )
        
        # ===== PRZED SZOKIEM (ryzyko jeszcze nie wzrosło) =====
        if days_to_shock > 0:
            roll = rng.random()
            if roll < config.pre_shock_risk_probability:
                return ArticleSignal(
                    category=rng.choice(config.categories),
                    risk_score=float(rng.randint(*config.risk_range)),
                    confidence=round(rng.uniform(0.58, 0.88), 2),
                    sentiment="negative" if config.risk_range[1] >= 55 else "mixed",
                )
        
        # ===== PO SZOKU (powolny spadek ryzyka) =====
        if days_to_shock < 0:
            days_since_shock = abs(days_to_shock)
            # Exponential decay: decay(0) = 1.0, decay(45) ≈ 0.5, decay(90) ≈ 0.25
            # Używa tę samą half_life co ReputationScorer (45 dni)
            decay_factor = math.exp(-0.693 * days_since_shock / config.post_shock_recovery_days)
            adjusted_risk_prob = config.risk_probability * decay_factor
            
            roll = rng.random()
            if roll < adjusted_risk_prob:
                return ArticleSignal(
                    category=rng.choice(config.categories),
                    risk_score=float(rng.randint(*config.risk_range)),
                    confidence=round(rng.uniform(0.58, 0.88), 2),
                    sentiment="negative" if config.risk_range[1] >= 55 else "mixed",
                )
    
    else:
        # ===== BEZ SZOKU: bardzo czysta reputacja =====
        roll = rng.random()
        if roll < config.pre_shock_risk_probability:  # bardzo mało
            roll2 = rng.random()
            if roll2 < config.minor_probability:
                category = rng.choice([item for item in config.categories if item != "other"] or ["regulatory"])
                return ArticleSignal(
                    category=category,
                    risk_score=float(rng.randint(6, 18)),
                    confidence=round(rng.uniform(0.42, 0.68), 2),
                    sentiment="mixed",
                )
    
    # ===== DEFAULT: brak ryzyka =====
    return ArticleSignal(category="other", risk_score=0.0, confidence=0.72, sentiment="neutral")


def _published_at(start: datetime, days: int, per_company: int, index: int, rng: random.Random) -> tuple[datetime, int]:
    """
    Zwraca timestamp artykułu + numer dnia w timeline (0-270).
    Dzień jest używany w _article_signal() do logiki szoku.
    """
    day_offset = (days * index) / max(per_company - 1, 1)
    jitter_hours = rng.randint(0, 20)
    jitter_minutes = rng.randint(0, 59)
    published_at = start + timedelta(days=day_offset, hours=jitter_hours, minutes=jitter_minutes)
    latest_allowed = _utc_now() - timedelta(hours=1)
    if published_at > latest_allowed:
        published_at = latest_allowed - timedelta(minutes=rng.randint(0, 180))
    
    current_day = int(day_offset)  # Dzień w timeline [0, 270]
    return published_at, current_day


def _article_text(config: DemoCompany, signal: ArticleSignal, index: int, published_at: datetime) -> tuple[str, str]:
    company = config.name
    date_text = published_at.strftime("%Y-%m-%d")
    category = signal.category

    if signal.risk_score <= 0:
        title = f"{company}: neutralna publikacja branżowa i aktualizacja operacyjna"
        content = (
            f"{date_text}: Media branżowe opisują bieżące działania spółki {company}. "
            "Publikacja dotyczy wyników operacyjnych, inwestycji i komunikacji z rynkiem. "
            "W materiale nie pojawiają się potwierdzone zarzuty, sankcje ani wątki prania pieniędzy. "
            "Artykuł stanowi tło reputacyjne wykorzystywane do monitorowania zmian w czasie."
        )
        return title, content

    templates = {
        "corruption": (
            f"{company}: prokuratura bada możliwą korupcję i łapówkę przy kontrakcie",
            "W artykule pojawiają się zarzuty dotyczące korupcji, łapówki oraz decyzji zarządu. "
            "Śledztwo obejmuje analizę dokumentów przetargowych i przepływów finansowych. "
            "Spółka podkreśla, że współpracuje z organami i prowadzi wewnętrzny audyt compliance.",
        ),
        "sanctions": (
            f"{company}: kontrola kontrahentów po doniesieniach o sankcjach",
            "Publikacja wskazuje na ryzyko sankcji i relacje z podmiotami objętymi ograniczeniami. "
            "Analitycy zwracają uwagę na konieczność weryfikacji dostawców i dokumentacji eksportowej. "
            "Zarząd zapowiada przegląd procedur AML i list sankcyjnych.",
        ),
        "money_laundering": (
            f"{company}: podejrzenia prania pieniędzy w sieci rozliczeń",
            "Media opisują podejrzenia prania pieniędzy oraz nietypowe transfery między rachunkami. "
            "Materiał wspomina o kontroli AML, analizie beneficjentów rzeczywistych i możliwym postępowaniu. "
            "Spółka deklaruje przekazanie dokumentów instytucjom nadzorczym.",
        ),
        "fraud": (
            f"{company}: klienci zgłaszają możliwe oszustwo i wyłudzenie",
            "Artykuł opisuje sygnały dotyczące oszustwa, wyłudzenia i nieprawidłowych rozliczeń. "
            "Według źródeł sprawa trafiła do działu compliance oraz kancelarii obsługującej poszkodowanych. "
            "Firma zapowiada audyt i korektę procesów sprzedażowych.",
        ),
        "embezzlement": (
            f"{company}: audyt wykazał ryzyko defraudacji środków",
            "Publikacja dotyczy podejrzenia defraudacji, malwersacji oraz braku kontroli nad wydatkami. "
            "Opisano działania audytorów i możliwe zawiadomienie organów ścigania. "
            "Spółka informuje o zmianach w procedurach zatwierdzania płatności.",
        ),
        "legal": (
            f"{company}: nowe zarzuty i postępowanie wobec członków zarządu",
            "Media informują o zarzutach, postępowaniu prokuratury i możliwej odpowiedzialności zarządu. "
            "W materiale podkreślono, że sprawa może wpłynąć na ocenę reputacji i relacje z kontrahentami. "
            "Spółka nie przyznaje się do naruszeń i zapowiada wyjaśnienia.",
        ),
        "regulatory": (
            f"{company}: regulator analizuje procedury compliance",
            "Artykuł opisuje kontrolę regulatora, potencjalne kary administracyjne i niedociągnięcia compliance. "
            "W materiale pojawia się kontekst AML, nadzoru oraz jakości dokumentacji klientów. "
            "Spółka deklaruje wdrożenie zaleceń i dodatkowe szkolenia.",
        ),
        "governance": (
            f"{company}: napięcia w zarządzie i pytania o ład korporacyjny",
            "Publikacja wskazuje na ryzyko governance, konflikt interesów i decyzje zarządu. "
            "Komentatorzy zwracają uwagę na wpływ sprawy na reputację i transparentność spółki. "
            "Firma zapowiada przegląd polityk wewnętrznych.",
        ),
    }
    title, body = templates.get(category, templates["regulatory"])
    content = (
        f"{date_text}: {body} "
        f"Sygnał ma przypisaną wagę demo {signal.risk_score:.0f}/100 i służy do pokazania historii scoringu. "
        f"Numer publikacji demo: {index + 1}."
    )
    return title, content


def _index_companies(companies: Sequence[Company]) -> None:
    try:
        from elastic import init_index, index_company

        init_index()
        for company in companies:
            index_company(company)
    except Exception as exc:
        print(f"Elasticsearch indexing skipped: {exc}")


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


if __name__ == "__main__":
    main()
