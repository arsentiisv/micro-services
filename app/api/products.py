from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.models.database import get_db, Product, User, UserRole
from app.schemas.generated import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    PaginatedProductResponse
)
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/products", tags=["Products"])


def product_not_found():
    return JSONResponse(
        status_code=404,
        content={"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден по ID"}
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [UserRole.SELLER.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED", "message": "Not enough permissions"}
        )
        
    try:
        new_product = Product(
            name=product_in.name,
            description=product_in.description,
            price=product_in.price,
            stock=product_in.stock,
            category=product_in.category,
            status="ACTIVE",
            seller_id=current_user.id
        )
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)
        return new_product
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/{id}", response_model=ProductResponse)
async def get_product(id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Product).where(Product.id == id))
        product = result.scalar_one_or_none()

        if not product:
            return product_not_found()

        return product
    except Exception:
        return product_not_found()


@router.get("", response_model=PaginatedProductResponse)
async def list_products(
        page: int = 0,
        size: int = 20,
        status: str | None = None,
        category: str | None = None,
        db: AsyncSession = Depends(get_db)
):
    query = select(Product)

    if status:
        query = query.where(Product.status == status)
    if category:
        query = query.where(Product.category == category)

    count_query = select(func.count()).select_from(query.subquery())
    total_elements = await db.scalar(count_query) or 0

    query = query.offset(page * size).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedProductResponse(
        items=items,
        totalElements=total_elements,
        page=page,
        size=size
    )


@router.put("/{id}", response_model=ProductResponse)
async def update_product(
    id: str,
    product_in: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        result = await db.execute(select(Product).where(Product.id == id))
        product = result.scalar_one_or_none()

        if not product:
            return product_not_found()

        if current_user.role != UserRole.ADMIN.value and product.seller_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCESS_DENIED", "message": "Not enough permissions"}
            )

        update_data = product_in.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)

        await db.commit()
        await db.refresh(product)
        return product
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        result = await db.execute(select(Product).where(Product.id == id))
        product = result.scalar_one_or_none()

        if not product:
            return product_not_found()

        if current_user.role != UserRole.ADMIN.value and product.seller_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCESS_DENIED", "message": "Not enough permissions"}
            )

        product.status = "ARCHIVED"
        await db.commit()
        return None
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
