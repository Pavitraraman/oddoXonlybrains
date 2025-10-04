"""
Expense API endpoints for the Expense Management System.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database import get_db
from app.models import User, Expense, ExpenseCategory, Approval, Company
from app.schemas import (
    ExpenseCreate, ExpenseUpdate, Expense as ExpenseSchema, 
    ExpenseWithDetails, PaginationParams, PaginatedResponse
)
from app.auth import get_current_active_user, require_admin, require_manager_or_admin
from app.services.currency_service import currency_service
from app.services.approval_service import approval_service
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("/", response_model=ExpenseSchema)
async def create_expense(
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new expense."""
    try:
        # Get company base currency
        company = await db.get(Company, current_user.company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        # Convert amount to base currency if needed
        amount_in_base = await currency_service.convert_currency(
            amount=expense_data.amount,
            from_currency=expense_data.currency,
            to_currency=company.base_currency,
            rate_date=expense_data.expense_date,
            db=db
        )
        
        if amount_in_base is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to convert {expense_data.currency} to {company.base_currency}"
            )
        
        # Get exchange rate
        exchange_rate = await currency_service.get_exchange_rate(
            from_currency=expense_data.currency,
            to_currency=company.base_currency,
            rate_date=expense_data.expense_date,
            db=db
        )
        
        # Create expense
        expense = Expense(
            company_id=current_user.company_id,
            user_id=current_user.id,
            category_id=expense_data.category_id,
            description=expense_data.description,
            amount=expense_data.amount,
            currency=expense_data.currency,
            amount_in_base_currency=amount_in_base,
            exchange_rate=exchange_rate or 1.0,
            exchange_rate_date=expense_data.expense_date,
            expense_date=expense_data.expense_date,
            paid_by=expense_data.paid_by,
            remarks=expense_data.remarks,
            status="draft"
        )
        
        db.add(expense)
        await db.commit()
        await db.refresh(expense)
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(current_user.company_id),
            user_id=str(current_user.id),
            action="create",
            resource_type="expense",
            resource_id=str(expense.id),
            new_values=expense_data.dict(),
            db=db
        )
        
        logger.info(f"Created expense {expense.id} for user {current_user.id}")
        return expense
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create expense"
        )


@router.get("/", response_model=PaginatedResponse)
async def get_expenses(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Get expenses for the current user."""
    try:
        # Build query
        query = select(Expense).where(Expense.company_id == current_user.company_id)
        
        # Apply user filter (employees can only see their own expenses)
        if current_user.role == "employee":
            query = query.where(Expense.user_id == current_user.id)
        
        # Apply filters
        if status_filter:
            query = query.where(Expense.status == status_filter)
        
        if category_id:
            query = query.where(Expense.category_id == category_id)
        
        if start_date:
            query = query.where(Expense.expense_date >= start_date)
        
        if end_date:
            query = query.where(Expense.expense_date <= end_date)
        
        # Get total count
        count_query = select(func.count(Expense.id))
        for filter_condition in query.whereclause:
            count_query = count_query.where(filter_condition)
        
        count_result = await db.execute(count_query)
        total_count = count_result.scalar()
        
        # Get paginated results
        query = query.options(
            selectinload(Expense.user),
            selectinload(Expense.category),
            selectinload(Expense.approvals)
        ).order_by(desc(Expense.created_at))
        
        result = await db.execute(
            query.offset((pagination.page - 1) * pagination.size)
            .limit(pagination.size)
        )
        expenses = result.scalars().all()
        
        return PaginatedResponse(
            items=[ExpenseWithDetails.from_orm(expense) for expense in expenses],
            total=total_count,
            page=pagination.page,
            size=pagination.size,
            pages=(total_count + pagination.size - 1) // pagination.size
        )
        
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get expenses"
        )


@router.get("/{expense_id}", response_model=ExpenseWithDetails)
async def get_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific expense by ID."""
    try:
        # Build query
        query = select(Expense).where(
            and_(
                Expense.id == expense_id,
                Expense.company_id == current_user.company_id
            )
        )
        
        # Apply user filter for employees
        if current_user.role == "employee":
            query = query.where(Expense.user_id == current_user.id)
        
        query = query.options(
            selectinload(Expense.user),
            selectinload(Expense.category),
            selectinload(Expense.approvals).selectinload(Approval.approver)
        )
        
        result = await db.execute(query)
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        return ExpenseWithDetails.from_orm(expense)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get expense"
        )


@router.put("/{expense_id}", response_model=ExpenseSchema)
async def update_expense(
    expense_id: UUID,
    expense_data: ExpenseUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an expense."""
    try:
        # Get expense
        result = await db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.company_id == current_user.company_id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Check permissions
        if current_user.role == "employee" and expense.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Check if expense can be updated
        if expense.status not in ["draft"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense cannot be updated after submission"
            )
        
        # Store old values for audit
        old_values = {
            "description": expense.description,
            "amount": float(expense.amount),
            "currency": expense.currency,
            "expense_date": expense.expense_date.isoformat(),
            "paid_by": expense.paid_by,
            "remarks": expense.remarks
        }
        
        # Update fields
        update_data = expense_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(expense, field, value)
        
        # Recalculate base currency amount if amount or currency changed
        if "amount" in update_data or "currency" in update_data:
            company = await db.get(Company, current_user.company_id)
            amount_in_base = await currency_service.convert_currency(
                amount=expense.amount,
                from_currency=expense.currency,
                to_currency=company.base_currency,
                rate_date=expense.expense_date,
                db=db
            )
            
            if amount_in_base:
                expense.amount_in_base_currency = amount_in_base
        
        await db.commit()
        await db.refresh(expense)
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(current_user.company_id),
            user_id=str(current_user.id),
            action="update",
            resource_type="expense",
            resource_id=str(expense.id),
            old_values=old_values,
            new_values=update_data,
            db=db
        )
        
        logger.info(f"Updated expense {expense.id}")
        return expense
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating expense: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update expense"
        )


@router.post("/{expense_id}/submit")
async def submit_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit an expense for approval."""
    try:
        # Get expense
        result = await db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.company_id == current_user.company_id,
                    Expense.user_id == current_user.id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        if expense.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense is not in draft status"
            )
        
        # Update expense status
        expense.status = "pending"
        expense.submitted_at = datetime.utcnow()
        
        await db.commit()
        
        # Create approval workflow
        await approval_service.create_approval_workflow(expense, db)
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(current_user.company_id),
            user_id=str(current_user.id),
            action="update",
            resource_type="expense",
            resource_id=str(expense.id),
            old_values={"status": "draft"},
            new_values={"status": "pending", "submitted_at": expense.submitted_at.isoformat()},
            db=db
        )
        
        logger.info(f"Submitted expense {expense.id} for approval")
        return {"message": "Expense submitted for approval", "expense_id": str(expense.id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting expense: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit expense"
        )


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an expense."""
    try:
        # Get expense
        result = await db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.company_id == current_user.company_id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Check permissions
        if current_user.role == "employee" and expense.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Check if expense can be deleted
        if expense.status not in ["draft"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense cannot be deleted after submission"
            )
        
        # Store expense data for audit
        expense_data = {
            "description": expense.description,
            "amount": float(expense.amount),
            "currency": expense.currency,
            "status": expense.status
        }
        
        # Delete expense
        await db.delete(expense)
        await db.commit()
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(current_user.company_id),
            user_id=str(current_user.id),
            action="delete",
            resource_type="expense",
            resource_id=str(expense_id),
            old_values=expense_data,
            db=db
        )
        
        logger.info(f"Deleted expense {expense_id}")
        return {"message": "Expense deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete expense"
        )


@router.get("/{expense_id}/approvals", response_model=List[ApprovalSchema])
async def get_expense_approvals(
    expense_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get approvals for a specific expense."""
    try:
        # Check if user has access to this expense
        result = await db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.company_id == current_user.company_id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Check permissions
        if current_user.role == "employee" and expense.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get approvals
        result = await db.execute(
            select(Approval)
            .where(Approval.expense_id == expense_id)
            .options(selectinload(Approval.approver))
            .order_by(Approval.created_at)
        )
        approvals = result.scalars().all()
        
        return [ApprovalWithDetails.from_orm(approval) for approval in approvals]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense approvals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get expense approvals"
        )
