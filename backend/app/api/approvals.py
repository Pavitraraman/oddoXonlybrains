"""
Approval API endpoints for the Expense Management System.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Approval, Expense, ApprovalRule
from app.schemas import (
    ApprovalCreate, ApprovalUpdate, Approval as ApprovalSchema,
    ApprovalWithDetails, PaginationParams, PaginatedResponse, ApprovalStatus
)
from app.auth import get_current_active_user, require_manager_or_admin
from app.services.approval_service import approval_service
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("/pending", response_model=PaginatedResponse)
async def get_pending_approvals(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends()
):
    """Get pending approvals for the current user."""
    try:
        approvals, total_count = await approval_service.get_pending_approvals(
            approver=current_user,
            db=db,
            limit=pagination.size,
            offset=(pagination.page - 1) * pagination.size
        )
        
        return PaginatedResponse(
            items=[ApprovalWithDetails.from_orm(approval) for approval in approvals],
            total=total_count,
            page=pagination.page,
            size=pagination.size,
            pages=(total_count + pagination.size - 1) // pagination.size
        )
        
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending approvals"
        )


@router.get("/history", response_model=PaginatedResponse)
async def get_approval_history(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends()
):
    """Get approval history for the current user."""
    try:
        approvals, total_count = await approval_service.get_approval_history(
            approver=current_user,
            db=db,
            limit=pagination.size,
            offset=(pagination.page - 1) * pagination.size
        )
        
        return PaginatedResponse(
            items=[ApprovalWithDetails.from_orm(approval) for approval in approvals],
            total=total_count,
            page=pagination.page,
            size=pagination.size,
            pages=(total_count + pagination.size - 1) // pagination.size
        )
        
    except Exception as e:
        logger.error(f"Error getting approval history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get approval history"
        )


@router.post("/{approval_id}/approve")
async def approve_expense(
    approval_id: UUID,
    comments: Optional[str] = None,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve an expense."""
    try:
        success, error_message = await approval_service.process_approval(
            approval_id=str(approval_id),
            status=ApprovalStatus.approved,
            comments=comments,
            approver=current_user,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        logger.info(f"Approved expense via approval {approval_id}")
        return {"message": "Expense approved successfully", "approval_id": str(approval_id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving expense: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve expense"
        )


@router.post("/{approval_id}/reject")
async def reject_expense(
    approval_id: UUID,
    comments: Optional[str] = None,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject an expense."""
    try:
        success, error_message = await approval_service.process_approval(
            approval_id=str(approval_id),
            status=ApprovalStatus.rejected,
            comments=comments,
            approver=current_user,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        logger.info(f"Rejected expense via approval {approval_id}")
        return {"message": "Expense rejected", "approval_id": str(approval_id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting expense: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject expense"
        )


@router.get("/{approval_id}", response_model=ApprovalWithDetails)
async def get_approval(
    approval_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific approval by ID."""
    try:
        # Get approval
        result = await db.execute(
            select(Approval)
            .where(Approval.id == approval_id)
            .options(
                selectinload(Approval.approver),
                selectinload(Approval.expense).selectinload(Expense.user),
                selectinload(Approval.expense).selectinload(Expense.category)
            )
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found"
            )
        
        # Check permissions
        if (current_user.role == "employee" and 
            approval.expense.user_id != current_user.id and 
            approval.approver_id != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return ApprovalWithDetails.from_orm(approval)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting approval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get approval"
        )


@router.put("/{approval_id}", response_model=ApprovalSchema)
async def update_approval(
    approval_id: UUID,
    approval_data: ApprovalUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an approval (only comments can be updated after approval/rejection)."""
    try:
        # Get approval
        result = await db.execute(
            select(Approval).where(
                and_(
                    Approval.id == approval_id,
                    Approval.approver_id == current_user.id
                )
            )
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found or access denied"
            )
        
        # Store old values for audit
        old_values = {
            "comments": approval.comments,
            "status": approval.status.value
        }
        
        # Update fields
        update_data = approval_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(approval, field, value)
        
        await db.commit()
        await db.refresh(approval)
        
        # Log audit trail
        await audit_service.log_action(
            company_id=str(current_user.company_id),
            user_id=str(current_user.id),
            action="update",
            resource_type="approval",
            resource_id=str(approval.id),
            old_values=old_values,
            new_values=update_data,
            db=db
        )
        
        logger.info(f"Updated approval {approval.id}")
        return approval
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating approval: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update approval"
        )


@router.get("/statistics/dashboard")
async def get_approval_statistics(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Get approval statistics for dashboard."""
    try:
        from datetime import datetime
        
        start_datetime = datetime.fromisoformat(start_date) if start_date else None
        end_datetime = datetime.fromisoformat(end_date) if end_date else None
        
        stats = await approval_service.get_approval_statistics(
            approver=current_user,
            db=db,
            start_date=start_datetime,
            end_date=end_datetime
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting approval statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get approval statistics"
        )


@router.post("/bulk-approve")
async def bulk_approve_expenses(
    approval_ids: List[UUID],
    comments: Optional[str] = None,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk approve multiple expenses."""
    try:
        results = []
        success_count = 0
        
        for approval_id in approval_ids:
            try:
                success, error_message = await approval_service.process_approval(
                    approval_id=str(approval_id),
                    status=ApprovalStatus.approved,
                    comments=comments,
                    approver=current_user,
                    db=db
                )
                
                if success:
                    success_count += 1
                    results.append({
                        "approval_id": str(approval_id),
                        "status": "approved"
                    })
                else:
                    results.append({
                        "approval_id": str(approval_id),
                        "status": "failed",
                        "error": error_message
                    })
                    
            except Exception as e:
                results.append({
                    "approval_id": str(approval_id),
                    "status": "failed",
                    "error": str(e)
                })
        
        logger.info(f"Bulk approval completed: {success_count}/{len(approval_ids)} successful")
        
        return {
            "message": f"Bulk approval completed: {success_count}/{len(approval_ids)} successful",
            "total": len(approval_ids),
            "successful": success_count,
            "failed": len(approval_ids) - success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk approval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk approval"
        )


@router.post("/bulk-reject")
async def bulk_reject_expenses(
    approval_ids: List[UUID],
    comments: Optional[str] = None,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk reject multiple expenses."""
    try:
        results = []
        success_count = 0
        
        for approval_id in approval_ids:
            try:
                success, error_message = await approval_service.process_approval(
                    approval_id=str(approval_id),
                    status=ApprovalStatus.rejected,
                    comments=comments,
                    approver=current_user,
                    db=db
                )
                
                if success:
                    success_count += 1
                    results.append({
                        "approval_id": str(approval_id),
                        "status": "rejected"
                    })
                else:
                    results.append({
                        "approval_id": str(approval_id),
                        "status": "failed",
                        "error": error_message
                    })
                    
            except Exception as e:
                results.append({
                    "approval_id": str(approval_id),
                    "status": "failed",
                    "error": str(e)
                })
        
        logger.info(f"Bulk rejection completed: {success_count}/{len(approval_ids)} successful")
        
        return {
            "message": f"Bulk rejection completed: {success_count}/{len(approval_ids)} successful",
            "total": len(approval_ids),
            "successful": success_count,
            "failed": len(approval_ids) - success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk rejection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk rejection"
        )
