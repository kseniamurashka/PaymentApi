import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Payment


@pytest.fixture
def payment_payload(client: TestClient) -> dict[str, int | str]:
    tariffs = client.get("/tariffs").json()
    tariff = next(item for item in tariffs if item["title"] == "standard")
    return {
        "tariff_id": tariff["id"],
        "email": "student@example.com",
        "method": "card",
    }


@pytest.mark.parametrize(
    ("method", "months", "promo_code", "amount", "discount", "schedule"),
    [
        ("card", None, None, 1990000, 0, None),
        ("installment", 3, "kvitto10", 1791000, 199000, [597000, 597000, 597000]),
    ],
)
def test_create_and_get_payment(
    client: TestClient,
    payment_payload: dict[str, int | str],
    method: str,
    months: int | None,
    promo_code: str | None,
    amount: int,
    discount: int,
    schedule: list[int] | None,
) -> None:
    payload = payment_payload | {
        "method": method,
        "installment_months": months,
        "promo_code": promo_code,
    }

    created = client.post("/payments", json=payload)

    assert created.status_code == 201
    payment = created.json()
    assert payment["id"] > 0
    assert payment["status"] == "pending"
    assert payment["tariff_id"] == payload["tariff_id"]
    assert payment["email"] == payload["email"]
    assert payment["method"] == method
    assert payment["amount"] == amount
    assert payment["discount"] == discount
    assert payment["installment_months"] == months
    assert payment["schedule"] == schedule
    assert payment["created_at"]

    fetched = client.get(f"/payments/{payment['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == payment


def test_requests_without_key_create_separate_payments(
    client: TestClient,
    payment_payload: dict[str, int | str],
    db_session: Session,
) -> None:
    first = client.post("/payments", json=payment_payload)
    second = client.post("/payments", json=payment_payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert db_session.scalar(select(func.count()).select_from(Payment)) == 2


@pytest.mark.parametrize("simulate_conflict", [False, True])
def test_idempotency_prevents_duplicate_payment(
    client: TestClient,
    payment_payload: dict[str, int | str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    simulate_conflict: bool,
) -> None:
    headers = {"Idempotency-Key": "payment-test-key"}
    first = client.post("/payments", json=payment_payload, headers=headers)
    assert first.status_code == 201

    if simulate_conflict:
        from app import routes

        real_lookup = routes.find_payment_by_key
        lookup_calls = 0

        def miss_first_lookup(session: Session, key: str | None) -> Payment | None:
            nonlocal lookup_calls
            lookup_calls += 1
            # Simulate an initial lookup before another request saved the payment.
            if lookup_calls == 1:
                return None
            return real_lookup(session, key)

        monkeypatch.setattr(routes, "find_payment_by_key", miss_first_lookup)

    repeated = client.post("/payments", json=payment_payload, headers=headers)

    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    assert db_session.scalar(select(func.count()).select_from(Payment)) == 1
    assert db_session.scalar(select(Payment.idempotency_key)) == "payment-test-key"
    if simulate_conflict:
        assert lookup_calls == 2


@pytest.mark.parametrize(
    "invalid_fields",
    [{"promo_code": "UNKNOWN"}, {"method": "installment"}],
    ids=["unknown-promo", "missing-installment-months"],
)
def test_invalid_payment_is_not_saved(
    client: TestClient,
    payment_payload: dict[str, int | str],
    db_session: Session,
    invalid_fields: dict[str, str],
) -> None:
    response = client.post("/payments", json=payment_payload | invalid_fields)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert response.json()["detail"]
    assert db_session.scalar(select(func.count()).select_from(Payment)) == 0


def test_missing_payment_returns_404(client: TestClient) -> None:
    response = client.get("/payments/999999")

    assert response.status_code == 404
