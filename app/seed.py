from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tariff

TARIFFS = [
    {"title": "basic", "price": 990000},
    {"title": "standard", "price": 1990000},
    {"title": "premium", "price": 2990000},
]


def seed_tariffs(session: Session) -> None:
    existing_titles = set(session.scalars(select(Tariff.title)))

    for tariff in TARIFFS:
        if tariff["title"] not in existing_titles:
            new_tariff = Tariff(
                title=tariff["title"],
                price=tariff["price"],
            )
            session.add(new_tariff)

    session.commit()
