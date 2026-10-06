from pydantic import BaseModel, ConfigDict


class TariffResponse(BaseModel):
    id: int
    title: str
    price: int

    model_config = ConfigDict(from_attributes=True)
