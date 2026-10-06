from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tariff
from app.schemas import TariffResponse

router = APIRouter()


@router.get("/tariffs", response_model=list[TariffResponse])
def get_tariffs(
    session: Annotated[Session, Depends(get_db)],
) -> list[Tariff]:
    result = session.scalars(select(Tariff).order_by(Tariff.id))
    return list(result)
