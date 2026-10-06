from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment, Tariff
from app.schemas import PaymentCreated, PaymentResponse, TariffResponse
from app.services import build_schedule, calculate_amount

router = APIRouter()


def find_payment_by_key(
    session: Session,
    idempotency_key: str | None,
) -> Payment | None:
    if idempotency_key is None:
        return None

    return session.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )


@router.get("/tariffs", response_model=list[TariffResponse])
def get_tariffs(
    session: Annotated[Session, Depends(get_db)],
) -> list[Tariff]:
    tariffs = session.scalars(select(Tariff).order_by(Tariff.id))
    return list(tariffs)


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    data: PaymentCreated,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Payment:
    existing_payment = find_payment_by_key(session, idempotency_key)
    if existing_payment is not None:
        response.status_code = 200
        return existing_payment

    tariff = session.get(Tariff, data.tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    amount, discount = calculate_amount(tariff.price, data.promo_code)

    months = None
    schedule = None

    if data.method == "installment":
        assert data.installment_months is not None
        months = data.installment_months
        schedule = build_schedule(amount, months)

    payment = Payment(
        tariff_id=data.tariff_id,
        email=data.email,
        method=data.method,
        amount=amount,
        discount=discount,
        installment_months=months,
        schedule=schedule,
        idempotency_key=idempotency_key,
    )
    session.add(payment)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()

        existing_payment = find_payment_by_key(session, idempotency_key)
        if existing_payment is not None:
            response.status_code = 200
            return existing_payment
        raise

    session.refresh(payment)
    return payment


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    return payment
