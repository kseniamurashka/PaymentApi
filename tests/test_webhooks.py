import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Payment


@pytest.fixture
def payment_id(client: TestClient) -> int:
    tariff_id = client.get("/tariffs").json()[0]["id"]
    response = client.post(
        "/payments",
        json={
            "tariff_id": tariff_id,
            "email": "student@example.com",
            "method": "card",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def signed_request(payment_id: int, status: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps({"payment_id": payment_id, "status": status}, indent=2).encode()
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    return body, {"Content-Type": "application/json", "X-Signature": signature}


@pytest.mark.parametrize(
    ("current_status", "new_status"),
    [
        ("pending", "succeeded"),
        ("pending", "failed"),
        ("succeeded", "refunded"),
    ],
)
def test_signed_webhook_changes_status(
    client: TestClient,
    payment_id: int,
    db_session: Session,
    current_status: str,
    new_status: str,
) -> None:
    payment = db_session.get(Payment, payment_id)
    assert payment is not None
    payment.status = current_status
    db_session.commit()
    body, headers = signed_request(payment_id, new_status)

    response = client.post("/webhooks/bank", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"result": "ok"}
    assert (
        db_session.scalar(select(Payment.status).where(Payment.id == payment_id))
        == new_status
    )


@pytest.mark.parametrize(
    ("current_status", "new_status"),
    [
        ("pending", "pending"),
        ("pending", "refunded"),
        ("succeeded", "pending"),
        ("succeeded", "succeeded"),
        ("succeeded", "failed"),
        ("failed", "pending"),
        ("failed", "succeeded"),
        ("failed", "failed"),
        ("failed", "refunded"),
        ("refunded", "pending"),
        ("refunded", "succeeded"),
        ("refunded", "failed"),
        ("refunded", "refunded"),
    ],
)
def test_forbidden_transition_does_not_change_status(
    client: TestClient,
    payment_id: int,
    db_session: Session,
    current_status: str,
    new_status: str,
) -> None:
    payment = db_session.get(Payment, payment_id)
    assert payment is not None
    payment.status = current_status
    db_session.commit()
    body, headers = signed_request(payment_id, new_status)

    response = client.post("/webhooks/bank", content=body, headers=headers)

    assert response.status_code == 409
    assert response.json() == {"error": "invalid_transition"}
    assert (
        db_session.scalar(select(Payment.status).where(Payment.id == payment_id))
        == current_status
    )


@pytest.mark.parametrize("signature_case", ["missing", "wrong", "tampered-body"])
def test_invalid_signature_does_not_change_status(
    client: TestClient,
    payment_id: int,
    db_session: Session,
    signature_case: str,
) -> None:
    body, headers = signed_request(payment_id, "succeeded")
    if signature_case == "missing":
        headers.pop("X-Signature")
    elif signature_case == "wrong":
        headers["X-Signature"] = "0" * 64
    else:
        body = body.replace(b"succeeded", b"failed")

    response = client.post("/webhooks/bank", content=body, headers=headers)

    assert response.status_code == 401
    assert (
        db_session.scalar(select(Payment.status).where(Payment.id == payment_id))
        == "pending"
    )


def test_webhook_for_missing_payment_returns_404(client: TestClient) -> None:
    body, headers = signed_request(999999, "succeeded")

    response = client.post("/webhooks/bank", content=body, headers=headers)

    assert response.status_code == 404
