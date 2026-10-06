import pytest

from app.schemas import PaymentCreated
from app.services import build_schedule, calculate_amount


@pytest.mark.parametrize(
    ("price", "discounted_amount", "discount"),
    [
        (990000, 891000, 99000),
        (1990000, 1791000, 199000),
        (2990000, 2691000, 299000),
    ],
)
@pytest.mark.parametrize("promo_code", [None, "KVITTO10", "kvitto10"])
def test_calculate_amount(
    price: int,
    discounted_amount: int,
    discount: int,
    promo_code: str | None,
) -> None:
    payment = PaymentCreated(
        tariff_id=1,
        email="student@example.com",
        method="card",
        promo_code=promo_code,
    )

    amount, actual_discount = calculate_amount(price, payment.promo_code)

    expected = (price, 0) if promo_code is None else (discounted_amount, discount)
    assert (amount, actual_discount) == expected
    assert type(amount) is int
    assert type(actual_discount) is int


@pytest.mark.parametrize("amount", [990000, 1990000, 2990000, 891000, 1791000, 2691000])
@pytest.mark.parametrize("months", [3, 6, 12])
def test_schedule_preserves_amount_and_distributes_remainder(
    amount: int, months: int
) -> None:
    schedule = build_schedule(amount, months)

    assert len(schedule) == months
    assert sum(schedule) == amount
    assert all(type(payment) is int and payment > 0 for payment in schedule)
    assert max(schedule) - min(schedule) <= 1
    assert schedule == sorted(schedule, reverse=True)


def test_schedule_matches_assignment_example() -> None:
    assert build_schedule(1990000, 3) == [663334, 663333, 663333]
