import hashlib
import hmac
import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.models import Base, Payment


@pytest.fixture
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    # Отдельные соединения должны работать с одной временной файловой базой.
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'payments.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_concurrent_webhooks_do_not_overwrite_status(
    client: TestClient,
    db_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import routes

    tariff_id = client.get("/tariffs").json()[0]["id"]
    created = client.post(
        "/payments",
        json={
            "tariff_id": tariff_id,
            "email": "student@example.com",
            "method": "card",
        },
    )
    assert created.status_code == 201
    payment_id = created.json()["id"]
    barrier = Barrier(2)
    original_check = routes.is_transition_allowed

    def synchronized_check(current_status: str, new_status: str) -> bool:
        allowed = original_check(current_status, new_status)
        # Оба запроса должны прочитать pending до первого обновления.
        barrier.wait(timeout=10)
        return allowed

    monkeypatch.setattr(routes, "is_transition_allowed", synchronized_check)

    def send_webhook(status: str) -> tuple[str, Response]:
        body = json.dumps({"payment_id": payment_id, "status": status}).encode()
        signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        return status, client.post(
            "/webhooks/bank",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": signature},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(send_webhook, ["succeeded", "failed"]))

    assert sorted(response.status_code for _, response in results) == [200, 409]
    winner = next(status for status, response in results if response.status_code == 200)
    for _, response in results:
        expected = (
            {"result": "ok"}
            if response.status_code == 200
            else {"error": "invalid_transition"}
        )
        assert response.json() == expected

    with Session(db_engine) as session:
        payment = session.get(Payment, payment_id)
        assert payment is not None
        assert payment.status == winner
