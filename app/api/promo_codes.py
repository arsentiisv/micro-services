from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.database import get_db, PromoCode, User, UserRole
from app.schemas.generated import PromoCodeCreate, PromoCodeResponse
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/promo-codes", tags=["Promo Codes"])

@router.post("", response_model=PromoCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_promo_code(
    promo_in: PromoCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [UserRole.SELLER.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED", "message": "Not enough permissions"}
        )

    try:
        new_promo = PromoCode(
            code=promo_in.code,
            discount_type=promo_in.discount_type.value,
            discount_value=promo_in.discount_value,
            min_order_amount=promo_in.min_order_amount,
            max_uses=promo_in.max_uses,
            valid_from=promo_in.valid_from,
            valid_until=promo_in.valid_until,
            active=True
        )
        db.add(new_promo)
        await db.commit()
        await db.refresh(new_promo)
        return new_promo
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "PROMO_CODE_EXISTS", "message": "Promo code with this code already exists"}
        )
