from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.discounts import DiscountCodeCheck
from app.api.security import get_optional_account
from app.api.services.discounts import check_code

router = APIRouter(tags=["Discounts"])


@router.get("/discount-codes/{code}", response_model=DiscountCodeCheck)
async def check_discount_code(
    code: str = Path(min_length=3, max_length=20, examples=["PEARL100"]),
    account: CurrentAccount | None = Depends(get_optional_account),
    db: AsyncConnection = Depends(get_db),
):
    # A personal code works only for its own guest, so a logged-in guest is recognised by the token
    result = await check_code(db, code, customer_id=account.customer_id if account else None)
    if result is None:
        raise HTTPException(status_code=404, detail={"reason": "CODE_NOT_FOUND"})
    return result
