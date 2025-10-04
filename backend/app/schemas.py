"""
Pydantic schemas for the Expense Management System.
Defines data validation and serialization models for API requests/responses.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, validator, ConfigDict
from enum import Enum


# Enums
class UserRole(str, Enum):
    """User role enumeration."""
    admin = "admin"
    manager = "manager"
    employee = "employee"


class ExpenseStatus(str, Enum):
    """Expense status enumeration."""
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ApprovalType(str, Enum):
    """Approval type enumeration."""
    compulsory = "compulsory"
    necessary = "necessary"


class ApprovalStatus(str, Enum):
    """Approval status enumeration."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class NotificationType(str, Enum):
    """Notification type enumeration."""
    invite = "invite"
    password_reset = "password_reset"
    expense_submitted = "expense_submitted"
    expense_approved = "expense_approved"
    expense_rejected = "expense_rejected"
    overdue_approval = "overdue_approval"


class AuditAction(str, Enum):
    """Audit action enumeration."""
    create = "create"
    update = "update"
    delete = "delete"
    approve = "approve"
    reject = "reject"
    login = "login"
    logout = "logout"
    password_change = "password_change"
    invite_sent = "invite_sent"


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""
    created_at: datetime
    updated_at: datetime


# Company schemas
class CompanyBase(BaseSchema):
    """Base company schema."""
    name: str = Field(..., min_length=1, max_length=255)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    is_active: bool = Field(default=True)


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""
    pass


class CompanyUpdate(BaseSchema):
    """Schema for updating a company."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    base_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    is_active: Optional[bool] = None


class Company(CompanyBase, TimestampMixin):
    """Complete company schema."""
    id: UUID


# User schemas
class UserBase(BaseSchema):
    """Base user schema."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole
    is_active: bool = Field(default=True)


class UserCreate(UserBase):
    """Schema for creating a user."""
    company_id: UUID
    password: str = Field(..., min_length=8)


class UserUpdate(BaseSchema):
    """Schema for updating a user."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserInvite(BaseSchema):
    """Schema for inviting a user."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole


class User(UserBase, TimestampMixin):
    """Complete user schema."""
    id: UUID
    company_id: UUID
    must_change_password: bool
    last_login: Optional[datetime]
    created_by: Optional[UUID]


class UserWithCompany(User):
    """User schema with company information."""
    company: Company


# Authentication schemas
class LoginRequest(BaseSchema):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(BaseSchema):
    """Schema for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordChange(BaseSchema):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordReset(BaseSchema):
    """Schema for password reset."""
    token: str
    new_password: str = Field(..., min_length=8)


# Expense category schemas
class ExpenseCategoryBase(BaseSchema):
    """Base expense category schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = Field(default=True)


class ExpenseCategoryCreate(ExpenseCategoryBase):
    """Schema for creating an expense category."""
    pass


class ExpenseCategoryUpdate(BaseSchema):
    """Schema for updating an expense category."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ExpenseCategory(ExpenseCategoryBase, TimestampMixin):
    """Complete expense category schema."""
    id: UUID
    company_id: UUID
    created_by: UUID


# Approval rule schemas
class ApprovalRuleBase(BaseSchema):
    """Base approval rule schema."""
    category_id: Optional[UUID] = None
    user_id: UUID
    approval_type: ApprovalType
    is_sequential: bool = Field(default=False)
    order_index: int = Field(default=0)
    is_active: bool = Field(default=True)


class ApprovalRuleCreate(ApprovalRuleBase):
    """Schema for creating an approval rule."""
    pass


class ApprovalRuleUpdate(BaseSchema):
    """Schema for updating an approval rule."""
    category_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    approval_type: Optional[ApprovalType] = None
    is_sequential: Optional[bool] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class ApprovalRule(ApprovalRuleBase, TimestampMixin):
    """Complete approval rule schema."""
    id: UUID
    company_id: UUID
    created_by: UUID


# Expense schemas
class ExpenseBase(BaseSchema):
    """Base expense schema."""
    category_id: UUID
    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(..., min_length=3, max_length=3)
    expense_date: date
    paid_by: str = Field(..., min_length=1, max_length=100)
    remarks: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    """Schema for creating an expense."""
    pass


class ExpenseUpdate(BaseSchema):
    """Schema for updating an expense."""
    category_id: Optional[UUID] = None
    description: Optional[str] = Field(None, min_length=1)
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    expense_date: Optional[date] = None
    paid_by: Optional[str] = Field(None, min_length=1, max_length=100)
    remarks: Optional[str] = None


class Expense(ExpenseBase, TimestampMixin):
    """Complete expense schema."""
    id: UUID
    company_id: UUID
    user_id: UUID
    amount_in_base_currency: Decimal
    exchange_rate: Decimal
    exchange_rate_date: date
    receipt_url: Optional[str]
    status: ExpenseStatus
    submitted_at: Optional[datetime]


class ExpenseWithDetails(Expense):
    """Expense schema with related data."""
    user: User
    category: ExpenseCategory
    approvals: List["Approval"]


# Approval schemas
class ApprovalBase(BaseSchema):
    """Base approval schema."""
    comments: Optional[str] = None


class ApprovalCreate(ApprovalBase):
    """Schema for creating an approval."""
    expense_id: UUID
    status: ApprovalStatus


class ApprovalUpdate(BaseSchema):
    """Schema for updating an approval."""
    status: ApprovalStatus
    comments: Optional[str] = None


class Approval(ApprovalBase, TimestampMixin):
    """Complete approval schema."""
    id: UUID
    expense_id: UUID
    approver_id: UUID
    status: ApprovalStatus
    approved_at: Optional[datetime]


class ApprovalWithDetails(Approval):
    """Approval schema with related data."""
    approver: User
    expense: Expense


# Currency rate schemas
class CurrencyRateBase(BaseSchema):
    """Base currency rate schema."""
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    rate: Decimal = Field(..., gt=0, decimal_places=6)
    rate_date: date


class CurrencyRateCreate(CurrencyRateBase):
    """Schema for creating a currency rate."""
    pass


class CurrencyRate(CurrencyRateBase, TimestampMixin):
    """Complete currency rate schema."""
    id: UUID


# OCR result schemas
class OCRResultBase(BaseSchema):
    """Base OCR result schema."""
    receipt_url: str
    detected_amount: Optional[Decimal] = None
    detected_currency: Optional[str] = None
    detected_date: Optional[date] = None
    confidence_score: Optional[Decimal] = None
    raw_text: Optional[str] = None
    is_verified: bool = Field(default=False)


class OCRResultCreate(OCRResultBase):
    """Schema for creating an OCR result."""
    expense_id: Optional[UUID] = None


class OCRResult(OCRResultBase, TimestampMixin):
    """Complete OCR result schema."""
    id: UUID
    expense_id: Optional[UUID]


# Notification schemas
class NotificationBase(BaseSchema):
    """Base notification schema."""
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a notification."""
    user_id: UUID


class NotificationUpdate(BaseSchema):
    """Schema for updating a notification."""
    is_read: bool


class Notification(NotificationBase, TimestampMixin):
    """Complete notification schema."""
    id: UUID
    user_id: UUID
    is_read: bool
    read_at: Optional[datetime]


# Audit log schemas
class AuditLogBase(BaseSchema):
    """Base audit log schema."""
    action: AuditAction
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: Optional[UUID] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    """Schema for creating an audit log."""
    company_id: Optional[UUID] = None
    user_id: Optional[UUID] = None


class AuditLog(AuditLogBase, TimestampMixin):
    """Complete audit log schema."""
    id: UUID
    company_id: Optional[UUID]
    user_id: Optional[UUID]


# File upload schemas
class FileUploadResponse(BaseSchema):
    """Schema for file upload response."""
    filename: str
    url: str
    size: int
    content_type: str


# Report schemas
class ExpenseReportFilter(BaseSchema):
    """Schema for expense report filtering."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    user_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    status: Optional[ExpenseStatus] = None
    currency: Optional[str] = None


class ExpenseReport(BaseSchema):
    """Schema for expense report."""
    total_expenses: int
    total_amount: Decimal
    total_amount_base: Decimal
    currency_breakdown: Dict[str, Decimal]
    category_breakdown: Dict[str, Decimal]
    user_breakdown: Dict[str, Decimal]
    status_breakdown: Dict[str, int]


# Dashboard schemas
class DashboardStats(BaseSchema):
    """Schema for dashboard statistics."""
    total_expenses: int
    pending_approvals: int
    approved_expenses: int
    rejected_expenses: int
    total_amount: Decimal
    monthly_trend: List[Dict[str, Any]]


# Pagination schemas
class PaginationParams(BaseSchema):
    """Schema for pagination parameters."""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseSchema):
    """Schema for paginated responses."""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


# Update forward references
ExpenseWithDetails.model_rebuild()
ApprovalWithDetails.model_rebuild()

