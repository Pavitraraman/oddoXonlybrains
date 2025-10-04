"""
Approval workflow service for the Expense Management System.
Handles complex approval routing, status calculation, and workflow management.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from app.models import (
    Expense, Approval, ApprovalRule, User, ExpenseCategory, 
    Notification, AuditLog, ExpenseStatus, ApprovalStatus, ApprovalType
)
from app.schemas import AuditAction, NotificationType
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service for managing expense approval workflows."""
    
    def __init__(self):
        self.overdue_threshold_days = 3  # Consider approvals overdue after 3 days
    
    async def create_approval_workflow(
        self, 
        expense: Expense, 
        db: AsyncSession
    ) -> List[Approval]:
        """
        Create approval workflow for an expense based on rules.
        
        Args:
            expense: The expense to create workflow for
            db: Database session
            
        Returns:
            List[Approval]: List of created approval records
        """
        try:
            # Get approval rules for this expense's category
            approval_rules = await self._get_approval_rules(expense.category_id, expense.company_id, db)
            
            if not approval_rules:
                logger.warning(f"No approval rules found for category {expense.category_id}")
                return []
            
            # Sort rules by order_index for sequential processing
            approval_rules.sort(key=lambda x: x.order_index)
            
            approvals = []
            
            # Create approval records based on rules
            for rule in approval_rules:
                if not rule.is_active:
                    continue
                
                # Check if user is active and in same company
                approver = await self._get_user(rule.user_id, db)
                if not approver or not approver.is_active or approver.company_id != expense.company_id:
                    logger.warning(f"Approver {rule.user_id} not found or inactive")
                    continue
                
                approval = Approval(
                    expense_id=expense.id,
                    approver_id=rule.user_id,
                    status=ApprovalStatus.pending
                )
                
                db.add(approval)
                approvals.append(approval)
                
                # Send notification to approver
                await notification_service.create_notification(
                    user_id=rule.user_id,
                    type=NotificationType.expense_submitted,
                    title="New Expense Approval Required",
                    message=f"Expense '{expense.description}' requires your approval",
                    metadata={
                        "expense_id": str(expense.id),
                        "approval_type": rule.approval_type.value,
                        "amount": float(expense.amount),
                        "currency": expense.currency
                    },
                    db=db
                )
            
            await db.commit()
            
            # Log audit trail
            await audit_service.log_action(
                company_id=expense.company_id,
                user_id=expense.user_id,
                action=AuditAction.create,
                resource_type="approval_workflow",
                resource_id=expense.id,
                new_values={
                    "approval_count": len(approvals),
                    "rules_applied": [rule.id for rule in approval_rules]
                },
                db=db
            )
            
            logger.info(f"Created approval workflow for expense {expense.id} with {len(approvals)} approvals")
            return approvals
            
        except Exception as e:
            logger.error(f"Error creating approval workflow: {e}")
            await db.rollback()
            return []
    
    async def process_approval(
        self,
        approval_id: str,
        status: ApprovalStatus,
        comments: Optional[str],
        approver: User,
        db: AsyncSession
    ) -> Tuple[bool, Optional[str]]:
        """
        Process an individual approval decision.
        
        Args:
            approval_id: ID of the approval to process
            status: Approval status (approved/rejected)
            comments: Optional comments from approver
            approver: User making the approval decision
            db: Database session
            
        Returns:
            Tuple[bool, Optional[str]]: Success status and error message
        """
        try:
            # Get the approval record
            result = await db.execute(
                select(Approval)
                .where(Approval.id == approval_id, Approval.approver_id == approver.id)
                .options(selectinload(Approval.expense))
            )
            approval = result.scalar_one_or_none()
            
            if not approval:
                return False, "Approval not found or access denied"
            
            if approval.status != ApprovalStatus.pending:
                return False, "Approval has already been processed"
            
            # Update approval record
            approval.status = status
            approval.comments = comments
            approval.approved_at = datetime.utcnow()
            
            # Log audit trail
            await audit_service.log_action(
                company_id=approver.company_id,
                user_id=approver.id,
                action=AuditAction.approve if status == ApprovalStatus.approved else AuditAction.reject,
                resource_type="approval",
                resource_id=approval.id,
                old_values={"status": ApprovalStatus.pending.value},
                new_values={
                    "status": status.value,
                    "comments": comments,
                    "approved_at": approval.approved_at.isoformat()
                },
                db=db
            )
            
            # Calculate overall expense status
            expense_status = await self._calculate_expense_status(approval.expense, db)
            
            # Update expense status
            approval.expense.status = expense_status
            
            await db.commit()
            
            # Send notification to expense submitter
            await notification_service.create_notification(
                user_id=approval.expense.user_id,
                type=NotificationType.expense_approved if status == ApprovalStatus.approved else NotificationType.expense_rejected,
                title=f"Expense {'Approved' if status == ApprovalStatus.approved else 'Rejected'}",
                message=f"Your expense '{approval.expense.description}' has been {status.value}",
                metadata={
                    "expense_id": str(approval.expense.id),
                    "approver": f"{approver.first_name} {approver.last_name}",
                    "comments": comments
                },
                db=db
            )
            
            logger.info(f"Processed approval {approval_id} with status {status.value}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error processing approval: {e}")
            await db.rollback()
            return False, str(e)
    
    async def _calculate_expense_status(self, expense: Expense, db: AsyncSession) -> ExpenseStatus:
        """
        Calculate the overall status of an expense based on all approvals.
        
        Args:
            expense: The expense to calculate status for
            db: Database session
            
        Returns:
            ExpenseStatus: Calculated expense status
        """
        try:
            # Get all approvals for this expense
            result = await db.execute(
                select(Approval)
                .where(Approval.expense_id == expense.id)
                .options(selectinload(Approval.approver))
            )
            approvals = result.scalars().all()
            
            if not approvals:
                return ExpenseStatus.pending
            
            # Get approval rules for this expense
            result = await db.execute(
                select(ApprovalRule)
                .where(ApprovalRule.category_id == expense.category_id)
                .where(ApprovalRule.is_active == True)
            )
            rules = result.scalars().all()
            
            # Group approvals by type
            compulsory_approvals = []
            necessary_approvals = []
            
            for approval in approvals:
                # Find corresponding rule
                rule = next((r for r in rules if r.user_id == approval.approver_id), None)
                if rule:
                    if rule.approval_type == ApprovalType.compulsory:
                        compulsory_approvals.append(approval)
                    elif rule.approval_type == ApprovalType.necessary:
                        necessary_approvals.append(approval)
            
            # Check compulsory approvals first
            for approval in compulsory_approvals:
                if approval.status == ApprovalStatus.rejected:
                    return ExpenseStatus.rejected
                elif approval.status == ApprovalStatus.pending:
                    return ExpenseStatus.pending
            
            # Check if all compulsory approvals are approved
            compulsory_approved = sum(1 for a in compulsory_approvals if a.status == ApprovalStatus.approved)
            if compulsory_approved < len(compulsory_approvals):
                return ExpenseStatus.pending
            
            # Check necessary approvals (60% rule)
            if necessary_approvals:
                necessary_approved = sum(1 for a in necessary_approvals if a.status == ApprovalStatus.approved)
                necessary_rejected = sum(1 for a in necessary_approvals if a.status == ApprovalStatus.rejected)
                
                # Calculate approval percentage
                total_necessary = len(necessary_approvals)
                approval_percentage = (necessary_approved / total_necessary) * 100 if total_necessary > 0 else 0
                
                # Check if 60% threshold is met
                if approval_percentage < 60:
                    return ExpenseStatus.rejected
            
            # If we reach here, expense is approved
            return ExpenseStatus.approved
            
        except Exception as e:
            logger.error(f"Error calculating expense status: {e}")
            return ExpenseStatus.pending
    
    async def get_pending_approvals(
        self,
        approver: User,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Approval], int]:
        """
        Get pending approvals for a specific approver.
        
        Args:
            approver: The approver user
            db: Database session
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            Tuple[List[Approval], int]: List of approvals and total count
        """
        try:
            # Get pending approvals for this approver
            query = (
                select(Approval)
                .where(
                    and_(
                        Approval.approver_id == approver.id,
                        Approval.status == ApprovalStatus.pending
                    )
                )
                .options(
                    selectinload(Approval.expense).selectinload(Expense.user),
                    selectinload(Approval.expense).selectinload(Expense.category)
                )
                .order_by(Approval.created_at.desc())
            )
            
            # Get total count
            count_result = await db.execute(
                select(func.count(Approval.id)).where(
                    and_(
                        Approval.approver_id == approver.id,
                        Approval.status == ApprovalStatus.pending
                    )
                )
            )
            total_count = count_result.scalar()
            
            # Get paginated results
            result = await db.execute(query.offset(offset).limit(limit))
            approvals = result.scalars().all()
            
            return approvals, total_count
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {e}")
            return [], 0
    
    async def get_approval_history(
        self,
        approver: User,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Approval], int]:
        """
        Get approval history for a specific approver.
        
        Args:
            approver: The approver user
            db: Database session
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            Tuple[List[Approval], int]: List of approvals and total count
        """
        try:
            # Get approval history for this approver
            query = (
                select(Approval)
                .where(Approval.approver_id == approver.id)
                .where(Approval.status != ApprovalStatus.pending)
                .options(
                    selectinload(Approval.expense).selectinload(Expense.user),
                    selectinload(Approval.expense).selectinload(Expense.category)
                )
                .order_by(Approval.approved_at.desc())
            )
            
            # Get total count
            count_result = await db.execute(
                select(func.count(Approval.id))
                .where(Approval.approver_id == approver.id)
                .where(Approval.status != ApprovalStatus.pending)
            )
            total_count = count_result.scalar()
            
            # Get paginated results
            result = await db.execute(query.offset(offset).limit(limit))
            approvals = result.scalars().all()
            
            return approvals, total_count
            
        except Exception as e:
            logger.error(f"Error getting approval history: {e}")
            return [], 0
    
    async def check_overdue_approvals(self, db: AsyncSession) -> List[Approval]:
        """
        Check for overdue approvals and send notifications.
        
        Args:
            db: Database session
            
        Returns:
            List[Approval]: List of overdue approvals
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.overdue_threshold_days)
            
            # Get overdue approvals
            result = await db.execute(
                select(Approval)
                .where(
                    and_(
                        Approval.status == ApprovalStatus.pending,
                        Approval.created_at < cutoff_date
                    )
                )
                .options(
                    selectinload(Approval.approver),
                    selectinload(Approval.expense)
                )
            )
            overdue_approvals = result.scalars().all()
            
            # Send overdue notifications
            for approval in overdue_approvals:
                await notification_service.create_notification(
                    user_id=approval.approver_id,
                    type=NotificationType.overdue_approval,
                    title="Overdue Approval Required",
                    message=f"Expense '{approval.expense.description}' approval is overdue",
                    metadata={
                        "expense_id": str(approval.expense.id),
                        "days_overdue": (datetime.utcnow() - approval.created_at).days
                    },
                    db=db
                )
            
            logger.info(f"Found {len(overdue_approvals)} overdue approvals")
            return overdue_approvals
            
        except Exception as e:
            logger.error(f"Error checking overdue approvals: {e}")
            return []
    
    async def _get_approval_rules(
        self, 
        category_id: str, 
        company_id: str, 
        db: AsyncSession
    ) -> List[ApprovalRule]:
        """Get approval rules for a category."""
        result = await db.execute(
            select(ApprovalRule)
            .where(
                and_(
                    ApprovalRule.category_id == category_id,
                    ApprovalRule.company_id == company_id,
                    ApprovalRule.is_active == True
                )
            )
            .order_by(ApprovalRule.order_index)
        )
        return result.scalars().all()
    
    async def _get_user(self, user_id: str, db: AsyncSession) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_approval_statistics(
        self,
        approver: User,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get approval statistics for an approver.
        
        Args:
            approver: The approver user
            db: Database session
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Dict[str, Any]: Approval statistics
        """
        try:
            # Build date filter
            date_filter = and_(
                Approval.approver_id == approver.id
            )
            
            if start_date:
                date_filter = and_(date_filter, Approval.created_at >= start_date)
            if end_date:
                date_filter = and_(date_filter, Approval.created_at <= end_date)
            
            # Get approval counts by status
            result = await db.execute(
                select(
                    Approval.status,
                    func.count(Approval.id).label('count')
                )
                .where(date_filter)
                .group_by(Approval.status)
            )
            
            status_counts = {row.status.value: row.count for row in result}
            
            # Get total pending approvals
            pending_result = await db.execute(
                select(func.count(Approval.id))
                .where(
                    and_(
                        Approval.approver_id == approver.id,
                        Approval.status == ApprovalStatus.pending
                    )
                )
            )
            total_pending = pending_result.scalar()
            
            # Get average approval time
            avg_time_result = await db.execute(
                select(func.avg(
                    func.extract('epoch', Approval.approved_at - Approval.created_at)
                ))
                .where(
                    and_(
                        Approval.approver_id == approver.id,
                        Approval.status != ApprovalStatus.pending,
                        Approval.approved_at.isnot(None)
                    )
                )
            )
            avg_approval_time_hours = avg_time_result.scalar() or 0
            
            return {
                "total_processed": sum(status_counts.values()),
                "pending": total_pending,
                "approved": status_counts.get(ApprovalStatus.approved.value, 0),
                "rejected": status_counts.get(ApprovalStatus.rejected.value, 0),
                "average_approval_time_hours": round(avg_approval_time_hours / 3600, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting approval statistics: {e}")
            return {
                "total_processed": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "average_approval_time_hours": 0
            }


# Global approval service instance
approval_service = ApprovalService()

