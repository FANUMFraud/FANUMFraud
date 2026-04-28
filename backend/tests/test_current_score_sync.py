from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Company, ScoreHistory
from pipeline.processor import sync_company_current_score


def test_current_score_uses_newest_history_point_when_inserted_out_of_order() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        company = Company(name="zondacrypto", current_score=96.0)
        db.add(company)
        db.flush()

        newer = datetime(2026, 4, 28, tzinfo=UTC).replace(tzinfo=None)
        older = newer - timedelta(days=2)

        db.add(
            ScoreHistory(
                company_id=company.id,
                article_id=None,
                score=38.0,
                risk_score=62.0,
                category="fraud",
                recorded_at=newer,
            )
        )
        db.add(
            ScoreHistory(
                company_id=company.id,
                article_id=None,
                score=91.0,
                risk_score=9.0,
                category="governance",
                recorded_at=older,
            )
        )

        synced_score = sync_company_current_score(db, company)

        assert synced_score == 38.0
        assert company.current_score == 38.0
