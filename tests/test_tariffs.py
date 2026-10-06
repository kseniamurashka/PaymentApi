from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tariff
from app.seed import seed_tariffs


def test_get_tariffs_returns_initial_data(client: TestClient) -> None:
    response = client.get("/tariffs")

    assert response.status_code == 200
    tariffs = response.json()
    assert len(tariffs) == 3
    assert {tariff["title"]: tariff["price"] for tariff in tariffs} == {
        "basic": 990000,
        "standard": 1990000,
        "premium": 2990000,
    }
    assert all(set(tariff) == {"id", "title", "price"} for tariff in tariffs)
    assert all(type(tariff["price"]) is int for tariff in tariffs)
    ids = [tariff["id"] for tariff in tariffs]
    assert all(type(tariff_id) is int and tariff_id > 0 for tariff_id in ids)
    assert len(set(ids)) == 3
    assert ids == sorted(ids)


def test_seed_tariffs_is_repeatable(db_session: Session) -> None:
    seed_tariffs(db_session)
    query = select(Tariff.id, Tariff.title, Tariff.price).order_by(Tariff.id)
    original = db_session.execute(query).all()

    seed_tariffs(db_session)

    assert len(original) == 3
    assert db_session.execute(query).all() == original


def test_seed_tariffs_preserves_existing_and_adds_missing(db_session: Session) -> None:
    existing = Tariff(title="basic", price=123456)
    db_session.add(existing)
    db_session.commit()
    original_id = existing.id

    seed_tariffs(db_session)

    tariffs = {tariff.title: tariff for tariff in db_session.scalars(select(Tariff))}
    assert set(tariffs) == {"basic", "standard", "premium"}
    assert tariffs["basic"].id == original_id
    assert tariffs["basic"].price == 123456
    assert tariffs["standard"].price == 1990000
    assert tariffs["premium"].price == 2990000
