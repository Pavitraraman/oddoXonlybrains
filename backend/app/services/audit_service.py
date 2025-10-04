"""
Audit logging service for the Expense Management System.
Handles comprehensive audit trails for all system actions and compliance.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from app.models import AuditLog, User, Company
from app.schemas import AuditAction, AuditLogCreate

logger = logging.getLogger(__name__)


class AuditService:
    """Service for managing audit logs and compliance tracking."""
    
    def __init__(self):
        self.retention_days = 365  # Keep audit logs for 1 year
    
    async def log_action(
        self,
        company_id: Optional[str],
        user_id: Optional[str],
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        db: AsyncSession = None
    ) -> AuditLog:
        """
        Log an audit action.
        
        Args:
            company_id: Company ID (optional)
            user_id: User ID (optional)
            action: Type of action performed
            resource_type: Type of resource affected
            resource_id: ID of the resource affected
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            ip_address: Client IP address
            user_agent: Client user agent
            db: Database session
            
        Returns:
            AuditLog: Created audit log entry
        """
        try:
            audit_log = AuditLog(
                company_id=company_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values or {},
                new_values=new_values or {},
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            db.add(audit_log)
            await db.commit()
            await db.refresh(audit_log)
            
            logger.debug(f"Logged audit action: {action.value} on {resource_type}")
            return audit_log
            
        except Exception as e:
            logger.error(f"Error logging audit action: {e}")
            await db.rollback()
            raise
    
    async def get_audit_logs(
        self,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        db: AsyncSession = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[AuditLog], int]:
        """
        Get audit logs with filtering options.
        
        Args:
            company_id: Filter by company ID
            user_id: Filter by user ID
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_date: Filter by start date
            end_date: Filter by end date
            db: Database session
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            tuple[List[AuditLog], int]: Audit logs and total count
        """
        try:
            # Build query
            query = select(AuditLog)
            count_query = select(func.count(AuditLog.id))
            
            # Add filters
            filters = []
            
            if company_id:
                filters.append(AuditLog.company_id == company_id)
            
            if user_id:
                filters.append(AuditLog.user_id == user_id)
            
            if action:
                filters.append(AuditLog.action == action)
            
            if resource_type:
                filters.append(AuditLog.resource_type == resource_type)
            
            if resource_id:
                filters.append(AuditLog.resource_id == resource_id)
            
            if start_date:
                filters.append(AuditLog.created_at >= start_date)
            
            if end_date:
                filters.append(AuditLog.created_at <= end_date)
            
            if filters:
                query = query.where(and_(*filters))
                count_query = count_query.where(and_(*filters))
            
            # Order by creation date (newest first)
            query = query.order_by(desc(AuditLog.created_at))
            
            # Get total count
            count_result = await db.execute(count_query)
            total_count = count_result.scalar()
            
            # Get paginated results
            result = await db.execute(
                query.offset(offset).limit(limit)
                .options(
                    selectinload(AuditLog.user),
                    selectinload(AuditLog.company)
                )
            )
            audit_logs = result.scalars().all()
            
            return audit_logs, total_count
            
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return [], 0
    
    async def get_user_activity(
        self,
        user_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Get activity history for a specific user.
        
        Args:
            user_id: User ID
            db: Database session
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of results
            
        Returns:
            List[AuditLog]: User activity logs
        """
        try:
            filters = [AuditLog.user_id == user_id]
            
            if start_date:
                filters.append(AuditLog.created_at >= start_date)
            
            if end_date:
                filters.append(AuditLog.created_at <= end_date)
            
            result = await db.execute(
                select(AuditLog)
                .where(and_(*filters))
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
                .options(
                    selectinload(AuditLog.company)
                )
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting user activity: {e}")
            return []
    
    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        db: AsyncSession,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Get history for a specific resource.
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            db: Database session
            limit: Maximum number of results
            
        Returns:
            List[AuditLog]: Resource history logs
        """
        try:
            result = await db.execute(
                select(AuditLog)
                .where(
                    and_(
                        AuditLog.resource_type == resource_type,
                        AuditLog.resource_id == resource_id
                    )
                )
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
                .options(
                    selectinload(AuditLog.user),
                    selectinload(AuditLog.company)
                )
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting resource history: {e}")
            return []
    
    async def get_company_audit_summary(
        self,
        company_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit summary for a company.
        
        Args:
            company_id: Company ID
            db: Database session
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict[str, Any]: Audit summary statistics
        """
        try:
            filters = [AuditLog.company_id == company_id]
            
            if start_date:
                filters.append(AuditLog.created_at >= start_date)
            
            if end_date:
                filters.append(AuditLog.created_at <= end_date)
            
            # Get action counts
            result = await db.execute(
                select(
                    AuditLog.action,
                    func.count(AuditLog.id).label('count')
                )
                .where(and_(*filters))
                .group_by(AuditLog.action)
            )
            
            action_counts = {row.action.value: row.count for row in result}
            
            # Get resource type counts
            result = await db.execute(
                select(
                    AuditLog.resource_type,
                    func.count(AuditLog.id).label('count')
                )
                .where(and_(*filters))
                .group_by(AuditLog.resource_type)
            )
            
            resource_counts = {row.resource_type: row.count for row in result}
            
            # Get user activity counts
            result = await db.execute(
                select(
                    AuditLog.user_id,
                    func.count(AuditLog.id).label('count')
                )
                .where(and_(*filters))
                .group_by(AuditLog.user_id)
                .order_by(desc('count'))
                .limit(10)
            )
            
            top_users = [
                {
                    "user_id": row.user_id,
                    "action_count": row.count
                }
                for row in result
            ]
            
            # Get total count
            result = await db.execute(
                select(func.count(AuditLog.id))
                .where(and_(*filters))
            )
            total_actions = result.scalar() or 0
            
            return {
                "total_actions": total_actions,
                "action_breakdown": action_counts,
                "resource_breakdown": resource_counts,
                "top_users": top_users,
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting company audit summary: {e}")
            return {
                "total_actions": 0,
                "action_breakdown": {},
                "resource_breakdown": {},
                "top_users": [],
                "date_range": {}
            }
    
    async def cleanup_old_logs(
        self,
        db: AsyncSession,
        days_old: Optional[int] = None
    ) -> int:
        """
        Clean up old audit logs based on retention policy.
        
        Args:
            db: Database session
            days_old: Number of days old (defaults to retention_days)
            
        Returns:
            int: Number of logs deleted
        """
        try:
            if days_old is None:
                days_old = self.retention_days
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Get count of logs to delete
            count_result = await db.execute(
                select(func.count(AuditLog.id))
                .where(AuditLog.created_at < cutoff_date)
            )
            count = count_result.scalar() or 0
            
            # Delete old logs
            if count > 0:
                await db.execute(
                    AuditLog.__table__.delete().where(
                        AuditLog.created_at < cutoff_date
                    )
                )
                await db.commit()
            
            logger.info(f"Cleaned up {count} old audit logs")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up old audit logs: {e}")
            await db.rollback()
            return 0
    
    async def export_audit_logs(
        self,
        company_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "csv"
    ) -> str:
        """
        Export audit logs for a company.
        
        Args:
            company_id: Company ID
            db: Database session
            start_date: Start date filter
            end_date: End date filter
            format: Export format (csv, json)
            
        Returns:
            str: Export data
        """
        try:
            # Get all audit logs for the company
            filters = [AuditLog.company_id == company_id]
            
            if start_date:
                filters.append(AuditLog.created_at >= start_date)
            
            if end_date:
                filters.append(AuditLog.created_at <= end_date)
            
            result = await db.execute(
                select(AuditLog)
                .where(and_(*filters))
                .order_by(desc(AuditLog.created_at))
                .options(
                    selectinload(AuditLog.user),
                    selectinload(AuditLog.company)
                )
            )
            
            audit_logs = result.scalars().all()
            
            if format.lower() == "csv":
                return self._export_to_csv(audit_logs)
            elif format.lower() == "json":
                return self._export_to_json(audit_logs)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting audit logs: {e}")
            return ""
    
    def _export_to_csv(self, audit_logs: List[AuditLog]) -> str:
        """Export audit logs to CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "Company ID", "User ID", "Action", "Resource Type", "Resource ID",
            "Old Values", "New Values", "IP Address", "User Agent", "Created At"
        ])
        
        # Write data
        for log in audit_logs:
            writer.writerow([
                str(log.id),
                str(log.company_id) if log.company_id else "",
                str(log.user_id) if log.user_id else "",
                log.action.value,
                log.resource_type,
                str(log.resource_id) if log.resource_id else "",
                str(log.old_values),
                str(log.new_values),
                str(log.ip_address) if log.ip_address else "",
                log.user_agent or "",
                log.created_at.isoformat()
            ])
        
        return output.getvalue()
    
    def _export_to_json(self, audit_logs: List[AuditLog]) -> str:
        """Export audit logs to JSON format."""
        import json
        
        data = []
        for log in audit_logs:
            data.append({
                "id": str(log.id),
                "company_id": str(log.company_id) if log.company_id else None,
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action.value,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat(),
                "user": {
                    "first_name": log.user.first_name,
                    "last_name": log.user.last_name,
                    "email": log.user.email
                } if log.user else None,
                "company": {
                    "name": log.company.name
                } if log.company else None
            })
        
        return json.dumps(data, indent=2)


# Global audit service instance
audit_service = AuditService()

