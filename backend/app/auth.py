"""
Authentication and authorization utilities for the Expense Management System.
Handles JWT tokens, password hashing, and role-based access control.
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from app.database import get_db
from app.models import User, Company
from app.schemas import UserRole

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token security
security = HTTPBearer()


class AuthManager:
    """Authentication manager for handling user authentication and authorization."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain password against its hash.
        
        Args:
            plain_password: The plain text password
            hashed_password: The hashed password
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """
        Hash a password.
        
        Args:
            password: The plain text password
            
        Returns:
            str: The hashed password
        """
        return pwd_context.hash(password)
    
    def generate_random_password(self, length: int = 12) -> str:
        """
        Generate a random password.
        
        Args:
            length: Length of the password
            
        Returns:
            str: Random password
        """
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time
            
        Returns:
            str: JWT access token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            data: Data to encode in the token
            
        Returns:
            str: JWT refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: The JWT token to verify
            token_type: Type of token (access or refresh)
            
        Returns:
            Dict[str, Any]: Decoded token data
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def create_token_pair(self, user_id: str, company_id: str, role: str) -> Dict[str, str]:
        """
        Create both access and refresh tokens for a user.
        
        Args:
            user_id: User ID
            company_id: Company ID
            role: User role
            
        Returns:
            Dict[str, str]: Token pair with access and refresh tokens
        """
        token_data = {
            "sub": str(user_id),
            "company_id": str(company_id),
            "role": role
        }
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60
        }


# Global auth manager instance
auth_manager = AuthManager()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user.
    
    Args:
        credentials: HTTP authorization credentials
        db: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If user is not authenticated or not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = auth_manager.verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current active user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Current active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(allowed_roles: list[UserRole]):
    """
    Decorator to require specific user roles.
    
    Args:
        allowed_roles: List of allowed user roles
        
    Returns:
        Decorator function
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Require admin role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Current user if admin
        
    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_manager_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Require manager or admin role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Current user if manager or admin
        
    Raises:
        HTTPException: If user is not manager or admin
    """
    if current_user.role not in [UserRole.manager, UserRole.admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required"
        )
    return current_user


async def get_current_company(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Company:
    """
    Get the current user's company.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Company: User's company
        
    Raises:
        HTTPException: If company is not found
    """
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id, Company.is_active == True)
    )
    company = result.scalar_one_or_none()
    
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return company


def verify_company_access(user: User, company_id: str) -> bool:
    """
    Verify if user has access to a specific company.
    
    Args:
        user: User to check
        company_id: Company ID to check access for
        
    Returns:
        bool: True if user has access, False otherwise
    """
    return str(user.company_id) == str(company_id)


def verify_user_access(user: User, target_user_id: str) -> bool:
    """
    Verify if user has access to another user's data.
    
    Args:
        user: Current user
        target_user_id: Target user ID
        
    Returns:
        bool: True if user has access, False otherwise
    """
    # Admin can access all users in their company
    if user.role == UserRole.admin:
        return True
    
    # Users can access their own data
    return str(user.id) == str(target_user_id)


async def authenticate_user(email: str, password: str, db: AsyncSession) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Args:
        email: User email
        password: User password
        db: Database session
        
    Returns:
        Optional[User]: User if authentication successful, None otherwise
    """
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    if not auth_manager.verify_password(password, user.password_hash):
        return None
    
    return user

