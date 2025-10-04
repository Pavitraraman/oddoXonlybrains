"""
SQLAlchemy models for the Expense Management System.
Defines all database entities with proper relationships and constraints.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Text, ForeignKey,
    Numeric, Integer, Enum, JSON, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, INET
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.schemas import (
    UserRole, ExpenseStatus, ApprovalType, ApprovalStatus,
    NotificationType, AuditAction
)


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Company(Base, TimestampMixin):
    """Company entity - represents organizations using the system."""
    __tablename__ = "companies"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="company", cascade="all, delete-orphan")
    expense_categories: Mapped[List["ExpenseCategory"]] = relationship("ExpenseCategory", back_populates="company", cascade="all, delete-orphan")
    approval_rules: Mapped[List["ApprovalRule"]] = relationship("ApprovalRule", back_populates="company", cascade="all, delete-orphan")
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="company", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="company")
    
    __table_args__ = (
        Index("idx_companies_name", "name"),
    )


class User(Base, TimestampMixin):
    """User entity - represents system users with role-based access."""
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="users")
    created_by_user: Mapped[Optional["User"]] = relationship("User", remote_side=[id])
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    approvals: Mapped[List["Approval"]] = relationship("Approval", back_populates="approver", cascade="all, delete-orphan")
    approval_rules: Mapped[List["ApprovalRule"]] = relationship("ApprovalRule", back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")
    
    __table_args__ = (
        Index("idx_users_company_email", "company_id", "email"),
        Index("idx_users_role", "role"),
        UniqueConstraint("company_id", "email", name="uq_users_company_email"),
    )


class ExpenseCategory(Base, TimestampMixin):
    """Expense category entity - managed by admin for expense classification."""
    __tablename__ = "expense_categories"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="expense_categories")
    created_by_user: Mapped["User"] = relationship("User")
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="category", cascade="all, delete-orphan")
    approval_rules: Mapped[List["ApprovalRule"]] = relationship("ApprovalRule", back_populates="category", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_expense_categories_company", "company_id"),
        UniqueConstraint("company_id", "name", name="uq_expense_categories_company_name"),
    )


class ApprovalRule(Base, TimestampMixin):
    """Approval rule entity - defines who can approve expenses in which categories."""
    __tablename__ = "approval_rules"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("expense_categories.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    approval_type: Mapped[ApprovalType] = mapped_column(Enum(ApprovalType), nullable=False)
    is_sequential: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="approval_rules")
    category: Mapped[Optional["ExpenseCategory"]] = relationship("ExpenseCategory", back_populates="approval_rules")
    user: Mapped["User"] = relationship("User", back_populates="approval_rules")
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_approval_rules_category", "category_id"),
        Index("idx_approval_rules_user", "user_id"),
        Index("idx_approval_rules_company", "company_id"),
    )


class Expense(Base, TimestampMixin):
    """Expense entity - represents individual expense submissions."""
    __tablename__ = "expenses"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("expense_categories.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_in_base_currency: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    exchange_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_by: Mapped[str] = mapped_column(String(100), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    receipt_url: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus), default=ExpenseStatus.draft)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="expenses")
    user: Mapped["User"] = relationship("User", back_populates="expenses")
    category: Mapped["ExpenseCategory"] = relationship("ExpenseCategory", back_populates="expenses")
    approvals: Mapped[List["Approval"]] = relationship("Approval", back_populates="expense", cascade="all, delete-orphan")
    ocr_results: Mapped[List["OCRResult"]] = relationship("OCRResult", back_populates="expense", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_expenses_user_status", "user_id", "status"),
        Index("idx_expenses_company_date", "company_id", "expense_date"),
        Index("idx_expenses_category", "category_id"),
        CheckConstraint("amount > 0", name="ck_expenses_positive_amount"),
        CheckConstraint("amount_in_base_currency > 0", name="ck_expenses_positive_base_amount"),
    )


class Approval(Base, TimestampMixin):
    """Approval entity - tracks individual approval actions on expenses."""
    __tablename__ = "approvals"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    expense_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    approver_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.pending)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    expense: Mapped["Expense"] = relationship("Expense", back_populates="approvals")
    approver: Mapped["User"] = relationship("User", back_populates="approvals")
    
    __table_args__ = (
        Index("idx_approvals_expense_status", "expense_id", "status"),
        Index("idx_approvals_approver", "approver_id", "status"),
        UniqueConstraint("expense_id", "approver_id", name="uq_approvals_expense_approver"),
    )


class CurrencyRate(Base, TimestampMixin):
    """Currency rate entity - stores exchange rates for currency conversion."""
    __tablename__ = "currency_rates"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    __table_args__ = (
        Index("idx_currency_rates_date", "rate_date"),
        Index("idx_currency_rates_currencies", "from_currency", "to_currency"),
        UniqueConstraint("from_currency", "to_currency", "rate_date", name="uq_currency_rates_unique"),
    )


class OCRResult(Base, TimestampMixin):
    """OCR result entity - stores OCR processing results for receipts."""
    __tablename__ = "ocr_results"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    expense_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"))
    receipt_url: Mapped[str] = mapped_column(String(500), nullable=False)
    detected_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    detected_currency: Mapped[Optional[str]] = mapped_column(String(3))
    detected_date: Mapped[Optional[date]] = mapped_column(Date)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    expense: Mapped[Optional["Expense"]] = relationship("Expense", back_populates="ocr_results")


class Notification(Base, TimestampMixin):
    """Notification entity - stores system notifications for users."""
    __tablename__ = "notifications"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    
    __table_args__ = (
        Index("idx_notifications_user_unread", "user_id", "is_read"),
    )


class AuditLog(Base, TimestampMixin):
    """Audit log entity - tracks all system actions for compliance."""
    __tablename__ = "audit_logs"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True))
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="audit_logs")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index("idx_audit_logs_company_date", "company_id", "created_at"),
        Index("idx_audit_logs_user_date", "user_id", "created_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
    )

