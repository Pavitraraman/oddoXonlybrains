"""
Main FastAPI application for the Expense Management System.
Provides comprehensive REST API endpoints for all system functionality.
"""

import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

from config import settings
from app.database import get_db, init_db, close_db
from app.models import User, Company, Expense, Approval, Notification
from app.schemas import (
    # Company schemas
    CompanyCreate, CompanyUpdate, Company as CompanySchema,
    # User schemas
    UserCreate, UserUpdate, UserInvite, User as UserSchema, UserWithCompany,
    # Auth schemas
    LoginRequest, Token, PasswordChange, PasswordReset,
    # Expense schemas
    ExpenseCategoryCreate, ExpenseCategoryUpdate, ExpenseCategory,
    ApprovalRuleCreate, ApprovalRuleUpdate, ApprovalRule,
    ExpenseCreate, ExpenseUpdate, Expense as ExpenseSchema, ExpenseWithDetails,
    ApprovalCreate, ApprovalUpdate, Approval as ApprovalSchema, ApprovalWithDetails,
    # Notification schemas
    Notification as NotificationSchema, NotificationUpdate,
    # Report schemas
    ExpenseReportFilter, ExpenseReport, DashboardStats,
    # Pagination schemas
    PaginationParams, PaginatedResponse,
    # File schemas
    FileUploadResponse,
    # Enums
    UserRole, ExpenseStatus, ApprovalStatus
)
from app.auth import (
    auth_manager, get_current_active_user, require_admin, require_manager_or_admin,
    verify_company_access, verify_user_access, authenticate_user
)

# Import API routers
from app.api import auth, expenses, approvals, notifications
from app.services.currency_service import currency_service
from app.services.ocr_service import ocr_service
from app.services.approval_service import approval_service
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Expense Management System...")
    await init_db()
    logger.info("Database initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Expense Management System...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Expense Management System",
    description="Enterprise-grade expense management system with role-based access control",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Include API routers
app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(approvals.router)
app.include_router(notifications.router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Authentication endpoints
@app.post("/auth/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return JWT tokens."""
    try:
        # Authenticate user
        user = await authenticate_user(login_data.email, login_data.password, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create tokens
        tokens = auth_manager.create_token_pair(
            user_id=str(user.id),
            company_id=str(user.company_id),
            role=user.role.value
        )
        
        # Update last login
        from datetime import datetime
        user.last_login = datetime.utcnow()
        await db.commit()
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(user.company_id),
            user_id=str(user.id),
            action="login",
            resource_type="user",
            resource_id=str(user.id),
            db=db
        )
        
        return tokens
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@app.post("/auth/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        payload = auth_manager.verify_token(refresh_token, "refresh")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new tokens
        tokens = auth_manager.create_token_pair(
            user_id=str(user.id),
            company_id=str(user.company_id),
            role=user.role.value
        )
        
        return tokens
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


# Company endpoints
@app.post("/companies", response_model=CompanySchema)
async def create_company(
    company_data: CompanyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new company (admin only)."""
    try:
        # Check if this is the first company (allow creation)
        result = await db.execute(select(Company))
        company_count = len(result.scalars().all())
        
        if company_count > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only one company is allowed in this system"
            )
        
        # Create company
        company = Company(
            name=company_data.name,
            base_currency=company_data.base_currency,
            is_active=company_data.is_active
        )
        
        db.add(company)
        await db.commit()
        await db.refresh(company)
        
        logger.info(f"Created company: {company.name}")
        return company
        
    except Exception as e:
        logger.error(f"Error creating company: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company"
        )


@app.get("/companies/current", response_model=CompanySchema)
async def get_current_company(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's company."""
    try:
        result = await db.execute(
            db.query(Company).where(
                Company.id == current_user.company_id,
                Company.is_active == True
            )
        )
        company = result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        return company
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get company"
        )


@app.put("/companies/current", response_model=CompanySchema)
async def update_company(
    company_data: CompanyUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update current company (admin only)."""
    try:
        result = await db.execute(
            db.query(Company).where(Company.id == current_user.company_id)
        )
        company = result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        # Update company fields
        if company_data.name is not None:
            company.name = company_data.name
        if company_data.base_currency is not None:
            company.base_currency = company_data.base_currency
        if company_data.is_active is not None:
            company.is_active = company_data.is_active
        
        await db.commit()
        await db.refresh(company)
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(company.id),
            user_id=str(current_user.id),
            action="update",
            resource_type="company",
            resource_id=str(company.id),
            new_values=company_data.dict(exclude_unset=True),
            db=db
        )
        
        return company
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company"
        )


# User management endpoints
@app.post("/users", response_model=UserSchema)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user (admin only)."""
    try:
        # Verify company access
        if not verify_company_access(current_user, str(user_data.company_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this company"
            )
        
        # Check if user already exists
        result = await db.execute(
            db.query(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create user
        user = User(
            company_id=user_data.company_id,
            email=user_data.email,
            password_hash=auth_manager.get_password_hash(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            is_active=user_data.is_active,
            created_by=current_user.id
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(user.company_id),
            user_id=str(current_user.id),
            action="create",
            resource_type="user",
            resource_id=str(user.id),
            new_values={
                "email": user.email,
                "role": user.role.value,
                "first_name": user.first_name,
                "last_name": user.last_name
            },
            db=db
        )
        
        logger.info(f"Created user: {user.email}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@app.post("/users/invite", response_model=UserSchema)
async def invite_user(
    user_data: UserInvite,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Invite a new user by email (admin only)."""
    try:
        # Check if user already exists
        result = await db.execute(
            db.query(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Generate temporary password
        temp_password = auth_manager.generate_random_password()
        
        # Create user
        user = User(
            company_id=current_user.company_id,
            email=user_data.email,
            password_hash=auth_manager.get_password_hash(temp_password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            must_change_password=True,
            created_by=current_user.id
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Send invitation email
        await notification_service.send_invitation_email(
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            temp_password=temp_password,
            db=db
        )
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(user.company_id),
            user_id=str(current_user.id),
            action="invite_sent",
            resource_type="user",
            resource_id=str(user.id),
            new_values={
                "email": user.email,
                "role": user.role.value
            },
            db=db
        )
        
        logger.info(f"Invited user: {user.email}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inviting user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite user"
        )


@app.get("/users", response_model=PaginatedResponse)
async def get_users(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends()
):
    """Get users for current company."""
    try:
        # Build query
        query = db.query(User).where(User.company_id == current_user.company_id)
        
        # Get total count
        count_result = await db.execute(
            query.with_entities(db.func.count(User.id))
        )
        total_count = count_result.scalar()
        
        # Get paginated results
        result = await db.execute(
            query.offset((pagination.page - 1) * pagination.size)
            .limit(pagination.size)
            .options(db.selectinload(User.company))
        )
        users = result.scalars().all()
        
        return PaginatedResponse(
            items=[UserWithCompany.from_orm(user) for user in users],
            total=total_count,
            page=pagination.page,
            size=pagination.size,
            pages=(total_count + pagination.size - 1) // pagination.size
        )
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )


@app.get("/users/{user_id}", response_model=UserWithCompany)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID."""
    try:
        # Verify access
        if not verify_user_access(current_user, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        result = await db.execute(
            db.query(User)
            .where(User.id == user_id, User.company_id == current_user.company_id)
            .options(db.selectinload(User.company))
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserWithCompany.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )


# Password management endpoints
@app.post("/auth/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password."""
    try:
        # Verify current password
        if not auth_manager.verify_password(password_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        current_user.password_hash = auth_manager.get_password_hash(password_data.new_password)
        current_user.must_change_password = False
        
        await db.commit()
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(current_user.company_id),
            user_id=str(current_user.id),
            action="password_change",
            resource_type="user",
            resource_id=str(current_user.id),
            db=db
        )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


# File upload endpoints
@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a file (receipt image)."""
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.allowed_extensions)}"
            )
        
        # Validate file size
        content = await file.read()
        if len(content) > settings.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {settings.max_file_size} bytes"
            )
        
        # Save file
        import uuid
        import os
        from pathlib import Path
        
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{file_ext}"
        file_path = Path(settings.upload_dir) / filename
        
        # Ensure upload directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, "wb") as f:
            f.write(content)
        
        return FileUploadResponse(
            filename=filename,
            url=f"/files/{filename}",
            size=len(content),
            content_type=file.content_type or "application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )


@app.get("/files/{filename}")
async def get_file(filename: str):
    """Get uploaded file."""
    try:
        file_path = Path(settings.upload_dir) / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return FileResponse(file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file"
        )


# OCR endpoints
@app.post("/ocr/process")
async def process_receipt_ocr(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Process receipt image with OCR."""
    try:
        # Save uploaded file temporarily
        import tempfile
        import uuid
        
        file_id = str(uuid.uuid4())
        file_ext = file.filename.split('.')[-1].lower()
        temp_filename = f"{file_id}.{file_ext}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Process with OCR
            ocr_result = await ocr_service.process_receipt(temp_path)
            
            return {
                "success": True,
                "data": ocr_result
            }
            
        finally:
            # Clean up temporary file
            import os
            os.unlink(temp_path)
        
    except Exception as e:
        logger.error(f"Error processing OCR: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process receipt"
        )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Expense Management System"}


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
