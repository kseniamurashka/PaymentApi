ALLOWED_TRANSITIONS = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"refunded"},
    "failed": set(),
    "refunded": set(),
}


def calculate_amount(price: int, promo_code: str | None) -> tuple[int, int]:
    if promo_code == "KVITTO10":
        discount = price // 10
    else:
        discount = 0
    amount = price - discount
    return amount, discount


def build_schedule(amount: int, months: int) -> list[int]:
    base_payment, remainder = divmod(amount, months)
    schedule = []
    for index in range(months):
        payment = base_payment
        if index < remainder:
            payment += 1
        schedule.append(payment)
    return schedule


def is_transition_allowed(current_status: str, new_status: str) -> bool:
    return new_status in ALLOWED_TRANSITIONS.get(current_status, set())
