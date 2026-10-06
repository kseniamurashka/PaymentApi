from datetime import datetime
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


class TariffResponse(BaseModel):
    id: int
    title: str
    price: int

    model_config = ConfigDict(from_attributes=True)


class PaymentCreated(BaseModel):
    tariff_id: int = Field(gt=0)
    email: EmailStr
    method: Literal["card", "sbp", "installment"]
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = None

    @model_validator(mode="after")
    def validate_installment(self) -> Self:
        if self.method == "installment" and self.installment_months is None:
            raise ValueError("Для рассрочки укажите срок: 3, 6 или 12 месяцев")
        return self

    @field_validator("promo_code")
    @classmethod
    def validate_promo_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.upper() != "KVITTO10":
            raise ValueError("Неизвестный промокод")
        return value.upper()


class PaymentResponse(BaseModel):
    id: int
    status: Literal["pending", "succeeded", "failed", "refunded"]
    tariff_id: int
    amount: int
    discount: int
    method: Literal["card", "sbp", "installment"]
    installment_months: int | None
    schedule: list[int] | None
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankWebhook(BaseModel):
    payment_id: int = Field(gt=0)
    status: Literal["pending", "succeeded", "failed", "refunded"]
