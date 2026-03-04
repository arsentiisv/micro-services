from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.models.database import get_db, User, UserRole
from app.schemas.generated import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    ErrorResponse
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Check if user exists
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "USER_EXISTS", "message": "User with this email already exists"}
        )
        
    hashed_password = security.get_password_hash(user_in.password)
    
    new_user = User(
        email=user_in.email,
        password_hash=hashed_password,
        role=user_in.role.value
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"message": "User registered successfully"}


@router.post("/login", response_model=TokenResponse)
async def login(
    user_in: UserLogin,
    db: AsyncSession = Depends(get_db)
) -> Any:
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Incorrect email or password"}
        )
        
    access_token = security.create_access_token(
        subject=user.id,
        role=user.role
    )
    refresh_token = security.create_refresh_token(
        subject=user.id,
        role=user.role
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_in: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    try:
        payload = security.jwt.decode(
            refresh_in.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        role = payload.get("role")
        token_type = payload.get("type")
        
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "TOKEN_INVALID", "message": "Invalid token type"}
            )
            
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "TOKEN_INVALID", "message": "Could not validate credentials"}
            )
            
    except (security.jwt.JWTError, security.ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "REFRESH_TOKEN_INVALID", "message": "Invalid refresh token"}
        )
        
    # Check if user still exists
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "USER_NOT_FOUND", "message": "User not found"}
        )
        
    access_token = security.create_access_token(
        subject=user.id,
        role=user.role
    )
    
    # Optionally rotate refresh token
    new_refresh_token = security.create_refresh_token(
        subject=user.id,
        role=user.role
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token
    }
