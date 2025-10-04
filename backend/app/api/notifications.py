"""
Notification API endpoints for the Expense Management System.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import (
    Notification as NotificationSchema, NotificationUpdate, 
    PaginationParams, PaginatedResponse, NotificationType
)
from app.auth import get_current_active_user
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=PaginatedResponse)
async def get_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
    unread_only: bool = Query(False),
    notification_type: Optional[NotificationType] = Query(None)
):
    """Get notifications for the current user."""
    try:
        if notification_type:
            notifications, total_count = await notification_service.get_notifications_by_type(
                user_id=str(current_user.id),
                notification_type=notification_type,
                db=db,
                limit=pagination.size,
                offset=(pagination.page - 1) * pagination.size
            )
        else:
            notifications, total_count = await notification_service.get_user_notifications(
                user_id=str(current_user.id),
                db=db,
                unread_only=unread_only,
                limit=pagination.size,
                offset=(pagination.page - 1) * pagination.size
            )
        
        return PaginatedResponse(
            items=[NotificationSchema.from_orm(notification) for notification in notifications],
            total=total_count,
            page=pagination.page,
            size=pagination.size,
            pages=(total_count + pagination.size - 1) // pagination.size
        )
        
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notifications"
        )


@router.get("/{notification_id}", response_model=NotificationSchema)
async def get_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific notification by ID."""
    try:
        notification = await notification_service.get_notification_by_id(
            notification_id=str(notification_id),
            user_id=str(current_user.id),
            db=db
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return NotificationSchema.from_orm(notification)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification"
        )


@router.put("/{notification_id}", response_model=NotificationSchema)
async def update_notification(
    notification_id: UUID,
    notification_data: NotificationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a notification."""
    try:
        success = await notification_service.update_notification(
            notification_id=str(notification_id),
            user_id=str(current_user.id),
            update_data=notification_data.dict(exclude_unset=True),
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or access denied"
            )
        
        # Get updated notification
        notification = await notification_service.get_notification_by_id(
            notification_id=str(notification_id),
            user_id=str(current_user.id),
            db=db
        )
        
        return NotificationSchema.from_orm(notification)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification"
        )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read."""
    try:
        success = await notification_service.mark_notification_read(
            notification_id=str(notification_id),
            user_id=str(current_user.id),
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or access denied"
            )
        
        return {"message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read for the current user."""
    try:
        updated_count = await notification_service.mark_all_notifications_read(
            user_id=str(current_user.id),
            db=db
        )
        
        return {
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read"
        )


@router.post("/mark-by-type-read")
async def mark_notifications_by_type_read(
    notification_type: NotificationType,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications of a specific type as read."""
    try:
        updated_count = await notification_service.mark_notifications_by_type_read(
            user_id=str(current_user.id),
            notification_type=notification_type,
            db=db
        )
        
        return {
            "message": f"Marked {updated_count} {notification_type.value} notifications as read",
            "updated_count": updated_count,
            "notification_type": notification_type.value
        }
        
    except Exception as e:
        logger.error(f"Error marking notifications by type as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications by type as read"
        )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a notification."""
    try:
        success = await notification_service.delete_notification(
            notification_id=str(notification_id),
            user_id=str(current_user.id),
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or access denied"
            )
        
        return {"message": "Notification deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )


@router.get("/unread/count")
async def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get count of unread notifications for the current user."""
    try:
        unread_count = await notification_service.get_unread_count(
            user_id=str(current_user.id),
            db=db
        )
        
        return {
            "unread_count": unread_count,
            "user_id": str(current_user.id)
        }
        
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count"
        )


@router.get("/recent/list")
async def get_recent_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    limit: int = Query(10, ge=1, le=50)
):
    """Get recent notifications for the current user."""
    try:
        notifications = await notification_service.get_recent_notifications(
            user_id=str(current_user.id),
            db=db,
            hours=hours,
            limit=limit
        )
        
        return {
            "notifications": [NotificationSchema.from_orm(n) for n in notifications],
            "count": len(notifications),
            "hours": hours,
            "user_id": str(current_user.id)
        }
        
    except Exception as e:
        logger.error(f"Error getting recent notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent notifications"
        )


@router.get("/statistics/summary")
async def get_notification_statistics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notification statistics for the current user."""
    try:
        stats = await notification_service.get_notification_statistics(
            user_id=str(current_user.id),
            db=db
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting notification statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification statistics"
        )


@router.get("/templates/list")
async def get_notification_templates():
    """Get available notification templates."""
    try:
        templates = await notification_service.get_notification_templates()
        return templates
        
    except Exception as e:
        logger.error(f"Error getting notification templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification templates"
        )
