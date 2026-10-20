from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.schemas.discounts import DiscountCodeCheck
from app.api.services.discounts import check_code

router = APIRouter(tags=["Discounts"])


@router.get("/discount-codes/{code}", response_model=DiscountCodeCheck)
async def check_discount_code(
    code: str = Path(min_length=3, max_length=20, examples=["PEARL100"]),
    db: AsyncConnection = Depends(get_db),
):
    # customer_id comes from the login (Thursday); until then personal codes answer PERSONAL_CODE_LOGIN_REQUIRED
    result = await check_code(db, code, customer_id=None)
    if result is None:
        raise HTTPException(status_code=404, detail={"reason": "CODE_NOT_FOUND"})
    return result
