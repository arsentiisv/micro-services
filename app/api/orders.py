import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db, Order, OrderItem, Product, PromoCode, UserOperation, User, UserRole
from app.schemas.generated import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderItemResponse,
    OrderStatus,
    DiscountType
)
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/orders", tags=["Orders"])


async def check_rate_limit(db: AsyncSession, user_id: uuid.UUID, operation_type: str):
    limit_minutes = 1
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=limit_minutes)
    
    query = select(UserOperation).where(
        and_(
            UserOperation.user_id == user_id,
            UserOperation.operation_type == operation_type,
            UserOperation.created_at >= cutoff_time
        )
    ).order_by(UserOperation.created_at.desc()).limit(1)
    
    result = await db.execute(query)
    last_op = result.scalar_one_or_none()
    
    if last_op:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "ORDER_LIMIT_EXCEEDED",
                "message": f"Please wait before creating another order (limit: {limit_minutes} min)"
            }
        )

async def check_active_orders(db: AsyncSession, user_id: uuid.UUID):
    query = select(Order).where(
        and_(
            Order.user_id == user_id,
            or_(
                Order.status == OrderStatus.CREATED.value,
                Order.status == OrderStatus.PAYMENT_PENDING.value
            )
        )
    )
    result = await db.execute(query)
    active_order = result.scalar_one_or_none()
    
    if active_order:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "ORDER_HAS_ACTIVE",
                "message": "User already has an active order"
            }
        )

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [UserRole.USER.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED", "message": "Only users and admins can create orders"}
        )

    await check_rate_limit(db, current_user.id, "CREATE_ORDER")
    
    await check_active_orders(db, current_user.id)
    
    async with db.begin():
        total_amount = Decimal("0.00")
        order_items_data = []
        
        for item in order_in.items:
            product_query = select(Product).where(Product.id == item.product_id).with_for_update()
            result = await db.execute(product_query)
            product = result.scalar_one_or_none()
            
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "PRODUCT_NOT_FOUND", "message": f"Product {item.product_id} not found"}
                )
            
            if product.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error_code": "PRODUCT_INACTIVE", "message": f"Product {product.name} is not active"}
                )
            
            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "INSUFFICIENT_STOCK",
                        "message": "Insufficient stock",
                        "details": {
                            "product_id": str(product.id),
                            "requested": item.quantity,
                            "available": product.stock
                        }
                    }
                )
            
            product.stock -= item.quantity
            db.add(product)
            
            price_at_order = product.price
            item_total = price_at_order * item.quantity
            total_amount += item_total
            
            order_items_data.append({
                "product_id": product.id,
                "quantity": item.quantity,
                "price_at_order": price_at_order
            })
        
        discount_amount = Decimal("0.00")
        promo_code_id = None
        
        if order_in.promo_code:
            promo_query = select(PromoCode).where(PromoCode.code == order_in.promo_code).with_for_update()
            result = await db.execute(promo_query)
            promo = result.scalar_one_or_none()
            
            now = datetime.now(timezone.utc)
            
            if not promo or not promo.active or promo.current_uses >= promo.max_uses or not (promo.valid_from <= now <= promo.valid_until):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error_code": "PROMO_CODE_INVALID", "message": "Promo code is invalid or expired"}
                )
            
            if total_amount < promo.min_order_amount:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error_code": "PROMO_CODE_MIN_AMOUNT", "message": f"Minimum order amount is {promo.min_order_amount}"}
                )
            
            if promo.discount_type == DiscountType.PERCENTAGE.value:
                discount = total_amount * (promo.discount_value / Decimal("100"))
                discount_amount = discount
            else:
                discount_amount = min(promo.discount_value, total_amount)
            
            promo.current_uses += 1
            db.add(promo)
            promo_code_id = promo.id
            
        final_amount = max(Decimal("0.00"), total_amount - discount_amount)
        
        new_order = Order(
            user_id=current_user.id,
            status=OrderStatus.CREATED.value,
            promo_code_id=promo_code_id,
            total_amount=final_amount,
            discount_amount=discount_amount
        )
        db.add(new_order)
        await db.flush()
        
        for item_data in order_items_data:
            new_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                price_at_order=item_data["price_at_order"]
            )
            db.add(new_item)
        
        op = UserOperation(
            user_id=current_user.id,
            operation_type="CREATE_ORDER"
        )
        db.add(op)

    query = select(Order).where(Order.id == new_order.id).options(selectinload(Order.items))
    result = await db.execute(query)
    created_order = result.scalar_one()
    
    return created_order

@router.get("/{id}", response_model=OrderResponse)
async def get_order(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = select(Order).where(Order.id == id).options(selectinload(Order.items))
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ORDER_NOT_FOUND", "message": "Order not found"}
        )
        
    if current_user.role != UserRole.ADMIN.value and order.user_id != current_user.id:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Access denied"}
        )
        
    return order

@router.post("/{id}/cancel", response_model=OrderResponse)
async def cancel_order(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    async with db.begin():
        query = select(Order).where(Order.id == id).with_for_update().options(selectinload(Order.items))
        result = await db.execute(query)
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ORDER_NOT_FOUND", "message": "Order not found"}
            )
            
        if current_user.role != UserRole.ADMIN.value and order.user_id != current_user.id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Access denied"}
            )
            
        if order.status not in [OrderStatus.CREATED.value, OrderStatus.PAYMENT_PENDING.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "INVALID_STATE_TRANSITION", "message": "Cannot cancel order in this state"}
            )
            
        for item in order.items:
            product_query = select(Product).where(Product.id == item.product_id).with_for_update()
            result = await db.execute(product_query)
            product = result.scalar_one_or_none()
            if product:
                product.stock += item.quantity
                db.add(product)
                
        if order.promo_code_id:
            promo_query = select(PromoCode).where(PromoCode.id == order.promo_code_id).with_for_update()
            result = await db.execute(promo_query)
            promo = result.scalar_one_or_none()
            if promo:
                promo.current_uses = max(0, promo.current_uses - 1)
                db.add(promo)
                
        order.status = OrderStatus.CANCELED.value
        db.add(order)
        
    query = select(Order).where(Order.id == id).options(selectinload(Order.items))
    result = await db.execute(query)
    updated_order = result.scalar_one()

    return updated_order
