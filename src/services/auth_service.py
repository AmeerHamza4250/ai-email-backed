"""
Authentication service.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import uuid
from src.models.user import User
from src.schemas.user import UserCreate, UserResponse, AuthResponse
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.BETTER_AUTH_SECRET or "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def hash_password(self, password: str) -> str:
        """Hash a password. Truncates to 72 bytes for bcrypt compatibility."""
        # Bcrypt has a 72-byte limit, so truncate if necessary
        # Truncate before encoding to avoid issues with multi-byte characters
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            # Truncate to 72 bytes, then decode safely
            truncated_bytes = password_bytes[:72]
            # Remove any incomplete UTF-8 sequences at the end
            while truncated_bytes and truncated_bytes[-1] & 0x80 and not (truncated_bytes[-1] & 0x40):
                truncated_bytes = truncated_bytes[:-1]
            password = truncated_bytes.decode('utf-8', errors='ignore')
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash. Truncates to 72 bytes for bcrypt compatibility."""
        # Bcrypt has a 72-byte limit, so truncate if necessary
        # Truncate before encoding to avoid issues with multi-byte characters
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            # Truncate to 72 bytes, then decode safely
            truncated_bytes = password_bytes[:72]
            # Remove any incomplete UTF-8 sequences at the end
            while truncated_bytes and truncated_bytes[-1] & 0x80 and not (truncated_bytes[-1] & 0x40):
                truncated_bytes = truncated_bytes[:-1]
            plain_password = truncated_bytes.decode('utf-8', errors='ignore')
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, user_id: str, tenant_id: str) -> str:
        """Create JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "exp": expire
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    async def create_user(self, user_data: UserCreate) -> dict:
        """Create a new user."""
        # Check if user already exists
        stmt = select(User).where(User.email == user_data.email)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create tenant_id (for multi-tenant, this could be from request or auto-generated)
        tenant_id = uuid.uuid4()
        
        # Create user
        hashed_password = self.hash_password(user_data.password)
        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            tenant_id=tenant_id,
            is_active=True
        )
        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        
        # Create token
        token = self.create_access_token(str(new_user.id), str(new_user.tenant_id))
        
        return {
            "token": token,
            "user": UserResponse.model_validate(new_user).model_dump()
        }
    
    async def authenticate_user(self, credentials: UserCreate) -> Optional[dict]:
        """Authenticate user and return token."""
        # Find user by email
        stmt = select(User).where(User.email == credentials.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Verify password
        if not self.verify_password(credentials.password, user.password_hash):
            return None
        
        # Check if user is active
        if not user.is_active:
            raise ValueError("User account is inactive")
        
        # Create token
        token = self.create_access_token(str(user.id), str(user.tenant_id))
        
        return {
            "token": token,
            "user": UserResponse.model_validate(user).model_dump()
        }

