"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.schemas.user import UserCreate, UserLogin, UserResponse
from src.services.auth_service import AuthService
from src.schemas.common import ApiResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/signup", response_model=ApiResponse)
async def signup(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user account."""
    try:
        auth_service = AuthService(db)
        result = await auth_service.create_user(user_data)
        return ApiResponse(
            status="success",
            message="User created successfully",
            data=result
        )
    except ValueError as e:
        logger.error("Signup error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unexpected signup error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/login", response_model=ApiResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login user and return JWT token."""
    try:
        auth_service = AuthService(db)
        result = await auth_service.authenticate_user(credentials)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        return ApiResponse(
            status="success",
            message="Login successful",
            data=result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected login error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

