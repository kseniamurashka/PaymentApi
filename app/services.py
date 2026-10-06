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
