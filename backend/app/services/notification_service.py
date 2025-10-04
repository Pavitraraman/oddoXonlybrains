"""
Notification service for the Expense Management System.
Handles email and in-app notifications for various system events.
"""

import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, update
from sqlalchemy.orm import selectinload

from config import settings
from app.models import Notification, User
from app.schemas import NotificationType, NotificationCreate, NotificationUpdate

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing system notifications."""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.email_from = settings.email_from
    
    async def create_notification(
        self,
        user_id: str,
        type: NotificationType,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        send_email: bool = True,
        db: AsyncSession = None
    ) -> Notification:
        """
        Create a new notification for a user.
        
        Args:
            user_id: ID of the user to notify
            type: Type of notification
            title: Notification title
            message: Notification message
            metadata: Optional metadata for the notification
            send_email: Whether to send email notification
            db: Database session
            
        Returns:
            Notification: Created notification
        """
        try:
            # Create notification record
            notification = Notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                metadata=metadata or {}
            )
            
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
            
            # Send email if requested and configured
            if send_email and self.smtp_username and self.smtp_password:
                await self._send_email_notification(user_id, title, message, db)
            
            logger.info(f"Created notification {notification.id} for user {user_id}")
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            await db.rollback()
            raise
    
    async def get_user_notifications(
        self,
        user_id: str,
        db: AsyncSession,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Notification], int]:
        """
        Get notifications for a user.
        
        Args:
            user_id: ID of the user
            db: Database session
            unread_only: Whether to return only unread notifications
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            tuple[List[Notification], int]: Notifications and total count
        """
        try:
            # Build query
            query = select(Notification).where(Notification.user_id == user_id)
            
            if unread_only:
                query = query.where(Notification.is_read == False)
            
            query = query.order_by(Notification.created_at.desc())
            
            # Get total count
            count_query = select(func.count(Notification.id)).where(Notification.user_id == user_id)
            if unread_only:
                count_query = count_query.where(Notification.is_read == False)
            
            count_result = await db.execute(count_query)
            total_count = count_result.scalar()
            
            # Get paginated results
            result = await db.execute(query.offset(offset).limit(limit))
            notifications = result.scalars().all()
            
            return notifications, total_count
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return [], 0
    
    async def mark_notification_read(
        self,
        notification_id: str,
        user_id: str,
        db: AsyncSession
    ) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            db: Database session
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update notification
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.id == notification_id,
                        Notification.user_id == user_id
                    )
                )
                .values(
                    is_read=True,
                    read_at=datetime.utcnow()
                )
            )
            
            if result.rowcount > 0:
                await db.commit()
                logger.info(f"Marked notification {notification_id} as read")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            await db.rollback()
            return False
    
    async def mark_all_notifications_read(
        self,
        user_id: str,
        db: AsyncSession
    ) -> int:
        """
        Mark all notifications as read for a user.
        
        Args:
            user_id: ID of the user
            db: Database session
            
        Returns:
            int: Number of notifications marked as read
        """
        try:
            # Update all unread notifications
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False
                    )
                )
                .values(
                    is_read=True,
                    read_at=datetime.utcnow()
                )
            )
            
            updated_count = result.rowcount
            await db.commit()
            
            logger.info(f"Marked {updated_count} notifications as read for user {user_id}")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            await db.rollback()
            return 0
    
    async def get_unread_count(self, user_id: str, db: AsyncSession) -> int:
        """
        Get count of unread notifications for a user.
        
        Args:
            user_id: ID of the user
            db: Database session
            
        Returns:
            int: Count of unread notifications
        """
        try:
            result = await db.execute(
                select(func.count(Notification.id))
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False
                    )
                )
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error getting unread notification count: {e}")
            return 0
    
    async def delete_old_notifications(
        self,
        days_old: int = 30,
        db: AsyncSession = None
    ) -> int:
        """
        Delete old notifications.
        
        Args:
            days_old: Delete notifications older than this many days
            db: Database session
            
        Returns:
            int: Number of notifications deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Get count of notifications to delete
            count_result = await db.execute(
                select(func.count(Notification.id))
                .where(Notification.created_at < cutoff_date)
            )
            count = count_result.scalar() or 0
            
            # Delete old notifications
            if count > 0:
                await db.execute(
                    Notification.__table__.delete().where(
                        Notification.created_at < cutoff_date
                    )
                )
                await db.commit()
            
            logger.info(f"Deleted {count} old notifications")
            return count
            
        except Exception as e:
            logger.error(f"Error deleting old notifications: {e}")
            await db.rollback()
            return 0
    
    async def _send_email_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        db: AsyncSession
    ) -> bool:
        """
        Send email notification to user.
        
        Args:
            user_id: ID of the user
            title: Email subject
            message: Email body
            db: Database session
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get user details
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user or not user.email:
                logger.warning(f"User {user_id} not found or has no email")
                return False
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = user.email
            msg['Subject'] = f"[Expense Management] {title}"
            
            # Create HTML email body
            html_body = f"""
            <html>
            <body>
                <h2>Expense Management System</h2>
                <p>Hello {user.first_name},</p>
                <p>{message}</p>
                <p>Please log in to the system to view details.</p>
                <br>
                <p>Best regards,<br>Expense Management System</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.email_from, user.email, text)
            server.quit()
            
            logger.info(f"Sent email notification to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    async def send_invitation_email(
        self,
        email: str,
        first_name: str,
        last_name: str,
        role: str,
        temp_password: str,
        db: AsyncSession = None
    ) -> bool:
        """
        Send invitation email to new user.
        
        Args:
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            role: User's role
            temp_password: Temporary password
            db: Database session
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = email
            msg['Subject'] = "[Expense Management] Account Invitation"
            
            # Create HTML email body
            html_body = f"""
            <html>
            <body>
                <h2>Welcome to Expense Management System</h2>
                <p>Hello {first_name} {last_name},</p>
                <p>You have been invited to join the Expense Management System as a {role}.</p>
                <p>Your temporary login credentials are:</p>
                <ul>
                    <li><strong>Email:</strong> {email}</li>
                    <li><strong>Password:</strong> {temp_password}</li>
                </ul>
                <p><strong>Important:</strong> You must change your password on first login.</p>
                <p>Please log in to the system to get started.</p>
                <br>
                <p>Best regards,<br>Expense Management System</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.email_from, email, text)
            server.quit()
            
            logger.info(f"Sent invitation email to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending invitation email: {e}")
            return False
    
    async def send_password_reset_email(
        self,
        email: str,
        first_name: str,
        reset_token: str,
        db: AsyncSession = None
    ) -> bool:
        """
        Send password reset email to user.
        
        Args:
            email: User's email address
            first_name: User's first name
            reset_token: Password reset token
            db: Database session
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = email
            msg['Subject'] = "[Expense Management] Password Reset"
            
            # Create HTML email body
            html_body = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Hello {first_name},</p>
                <p>You have requested a password reset for your Expense Management System account.</p>
                <p>Your reset token is: <strong>{reset_token}</strong></p>
                <p>Please use this token to reset your password in the system.</p>
                <p>If you did not request this reset, please contact your administrator.</p>
                <br>
                <p>Best regards,<br>Expense Management System</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.email_from, email, text)
            server.quit()
            
            logger.info(f"Sent password reset email to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending password reset email: {e}")
            return False


    async def send_bulk_notifications(
        self,
        notifications: List[Dict[str, Any]],
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Send multiple notifications in batch.
        
        Args:
            notifications: List of notification dictionaries
            db: Database session
            
        Returns:
            Dict[str, Any]: Batch sending results
        """
        try:
            logger.info(f"Sending {len(notifications)} bulk notifications")
            
            results = []
            success_count = 0
            
            for notification_data in notifications:
                try:
                    notification = await self.create_notification(
                        user_id=notification_data['user_id'],
                        type=notification_data['type'],
                        title=notification_data['title'],
                        message=notification_data['message'],
                        metadata=notification_data.get('metadata'),
                        send_email=notification_data.get('send_email', True),
                        db=db
                    )
                    results.append({'status': 'success', 'notification_id': str(notification.id)})
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error creating notification: {e}")
                    results.append({'status': 'error', 'message': str(e)})
            
            logger.info(f"Bulk notification sending completed. {success_count}/{len(notifications)} sent successfully.")
            
            return {
                'status': 'completed',
                'total': len(notifications),
                'successful': success_count,
                'failed': len(notifications) - success_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Bulk notification sending failed: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def get_notification_by_id(
        self,
        notification_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Optional[Notification]:
        """
        Get a specific notification by ID for a user.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            db: Database session
            
        Returns:
            Optional[Notification]: Notification if found, None otherwise
        """
        try:
            result = await db.execute(
                select(Notification)
                .where(
                    and_(
                        Notification.id == notification_id,
                        Notification.user_id == user_id
                    )
                )
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting notification by ID: {e}")
            return None
    
    async def update_notification(
        self,
        notification_id: str,
        user_id: str,
        update_data: Dict[str, Any],
        db: AsyncSession
    ) -> bool:
        """
        Update a notification.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            update_data: Data to update
            db: Database session
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.id == notification_id,
                        Notification.user_id == user_id
                    )
                )
                .values(**update_data)
            )
            
            if result.rowcount > 0:
                await db.commit()
                logger.info(f"Updated notification {notification_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error updating notification: {e}")
            await db.rollback()
            return False
    
    async def delete_notification(
        self,
        notification_id: str,
        user_id: str,
        db: AsyncSession
    ) -> bool:
        """
        Delete a notification.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            db: Database session
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = await db.execute(
                Notification.__table__.delete().where(
                    and_(
                        Notification.id == notification_id,
                        Notification.user_id == user_id
                    )
                )
            )
            
            if result.rowcount > 0:
                await db.commit()
                logger.info(f"Deleted notification {notification_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            await db.rollback()
            return False
    
    async def get_notifications_by_type(
        self,
        user_id: str,
        notification_type: NotificationType,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Notification], int]:
        """
        Get notifications by type for a user.
        
        Args:
            user_id: ID of the user
            notification_type: Type of notifications to get
            db: Database session
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            tuple[List[Notification], int]: Notifications and total count
        """
        try:
            # Build query
            query = select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.type == notification_type
                )
            )
            
            query = query.order_by(Notification.created_at.desc())
            
            # Get total count
            count_query = select(func.count(Notification.id)).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.type == notification_type
                )
            )
            
            count_result = await db.execute(count_query)
            total_count = count_result.scalar()
            
            # Get paginated results
            result = await db.execute(query.offset(offset).limit(limit))
            notifications = result.scalars().all()
            
            return notifications, total_count
            
        except Exception as e:
            logger.error(f"Error getting notifications by type: {e}")
            return [], 0
    
    async def send_test_email(
        self,
        email: str,
        db: AsyncSession = None
    ) -> bool:
        """
        Send a test email to verify SMTP configuration.
        
        Args:
            email: Email address to send test to
            db: Database session
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create test email message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = email
            msg['Subject'] = "[Expense Management] Test Email"
            
            # Create HTML email body
            html_body = """
            <html>
            <body>
                <h2>Test Email</h2>
                <p>This is a test email from the Expense Management System.</p>
                <p>If you received this email, your SMTP configuration is working correctly.</p>
                <br>
                <p>Best regards,<br>Expense Management System</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.email_from, email, text)
            server.quit()
            
            logger.info(f"Test email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending test email: {e}")
            return False
    
    async def get_notification_statistics(
        self,
        user_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get notification statistics for a user.
        
        Args:
            user_id: ID of the user
            db: Database session
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Dict[str, Any]: Notification statistics
        """
        try:
            # Build date filter
            filters = [Notification.user_id == user_id]
            
            if start_date:
                filters.append(Notification.created_at >= start_date)
            if end_date:
                filters.append(Notification.created_at <= end_date)
            
            date_filter = and_(*filters)
            
            # Get notification counts by type
            result = await db.execute(
                select(
                    Notification.type,
                    func.count(Notification.id).label('count')
                )
                .where(date_filter)
                .group_by(Notification.type)
            )
            
            type_counts = {row.type.value: row.count for row in result}
            
            # Get total notifications
            total_result = await db.execute(
                select(func.count(Notification.id)).where(date_filter)
            )
            total_notifications = total_result.scalar() or 0
            
            # Get unread count
            unread_result = await db.execute(
                select(func.count(Notification.id)).where(
                    and_(
                        date_filter,
                        Notification.is_read == False
                    )
                )
            )
            unread_count = unread_result.scalar() or 0
            
            # Get read count
            read_count = total_notifications - unread_count
            
            # Calculate read percentage
            read_percentage = (read_count / total_notifications * 100) if total_notifications > 0 else 0
            
            return {
                'total_notifications': total_notifications,
                'unread_count': unread_count,
                'read_count': read_count,
                'read_percentage': round(read_percentage, 2),
                'type_breakdown': type_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting notification statistics: {e}")
            return {
                'total_notifications': 0,
                'unread_count': 0,
                'read_count': 0,
                'read_percentage': 0,
                'type_breakdown': {}
            }
    
    async def mark_notifications_by_type_read(
        self,
        user_id: str,
        notification_type: NotificationType,
        db: AsyncSession
    ) -> int:
        """
        Mark all notifications of a specific type as read for a user.
        
        Args:
            user_id: ID of the user
            notification_type: Type of notifications to mark as read
            db: Database session
            
        Returns:
            int: Number of notifications marked as read
        """
        try:
            # Update notifications by type
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.type == notification_type,
                        Notification.is_read == False
                    )
                )
                .values(
                    is_read=True,
                    read_at=datetime.utcnow()
                )
            )
            
            updated_count = result.rowcount
            await db.commit()
            
            logger.info(f"Marked {updated_count} {notification_type.value} notifications as read for user {user_id}")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error marking notifications by type as read: {e}")
            await db.rollback()
            return 0
    
    async def create_system_notification(
        self,
        company_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        send_email: bool = False,
        db: AsyncSession = None
    ) -> int:
        """
        Create notifications for all users in a company.
        
        Args:
            company_id: ID of the company
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            metadata: Optional metadata
            send_email: Whether to send email notifications
            db: Database session
            
        Returns:
            int: Number of notifications created
        """
        try:
            # Get all active users in the company
            result = await db.execute(
                select(User).where(
                    and_(
                        User.company_id == company_id,
                        User.is_active == True
                    )
                )
            )
            users = result.scalars().all()
            
            notifications_created = 0
            
            for user in users:
                try:
                    notification = Notification(
                        user_id=str(user.id),
                        type=notification_type,
                        title=title,
                        message=message,
                        metadata=metadata or {}
                    )
                    
                    db.add(notification)
                    notifications_created += 1
                    
                    # Send email if requested
                    if send_email and user.email:
                        await self._send_email_notification(
                            user_id=str(user.id),
                            title=title,
                            message=message,
                            db=db
                        )
                        
                except Exception as e:
                    logger.error(f"Error creating notification for user {user.id}: {e}")
                    continue
            
            await db.commit()
            
            logger.info(f"Created {notifications_created} system notifications for company {company_id}")
            return notifications_created
            
        except Exception as e:
            logger.error(f"Error creating system notifications: {e}")
            await db.rollback()
            return 0
    
    async def get_recent_notifications(
        self,
        user_id: str,
        db: AsyncSession,
        hours: int = 24,
        limit: int = 10
    ) -> List[Notification]:
        """
        Get recent notifications for a user.
        
        Args:
            user_id: ID of the user
            db: Database session
            hours: Number of hours to look back
            limit: Maximum number of notifications to return
            
        Returns:
            List[Notification]: Recent notifications
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            result = await db.execute(
                select(Notification)
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.created_at >= cutoff_time
                    )
                )
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting recent notifications: {e}")
            return []
    
    async def archive_old_notifications(
        self,
        days_old: int = 90,
        db: AsyncSession = None
    ) -> int:
        """
        Archive old notifications (mark as archived instead of deleting).
        
        Args:
            days_old: Archive notifications older than this many days
            db: Database session
            
        Returns:
            int: Number of notifications archived
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Update old notifications to archived status
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.created_at < cutoff_date,
                        Notification.is_read == True  # Only archive read notifications
                    )
                )
                .values(metadata=func.jsonb_set(
                    Notification.metadata,
                    '{archived}',
                    'true'
                ))
            )
            
            archived_count = result.rowcount
            await db.commit()
            
            logger.info(f"Archived {archived_count} old notifications")
            return archived_count
            
        except Exception as e:
            logger.error(f"Error archiving old notifications: {e}")
            await db.rollback()
            return 0
    
    async def get_notification_templates(self) -> Dict[str, Dict[str, str]]:
        """
        Get predefined notification templates.
        
        Returns:
            Dict[str, Dict[str, str]]: Notification templates
        """
        return {
            'expense_submitted': {
                'title': 'New Expense Submitted',
                'message': 'A new expense has been submitted and requires your approval.',
                'email_subject': 'New Expense Approval Required'
            },
            'expense_approved': {
                'title': 'Expense Approved',
                'message': 'Your expense has been approved.',
                'email_subject': 'Expense Approved'
            },
            'expense_rejected': {
                'title': 'Expense Rejected',
                'message': 'Your expense has been rejected.',
                'email_subject': 'Expense Rejected'
            },
            'overdue_approval': {
                'title': 'Overdue Approval Required',
                'message': 'You have overdue expense approvals that require attention.',
                'email_subject': 'Overdue Approvals'
            },
            'password_reset': {
                'title': 'Password Reset',
                'message': 'You have requested a password reset.',
                'email_subject': 'Password Reset Request'
            },
            'invite': {
                'title': 'Account Invitation',
                'message': 'You have been invited to join the Expense Management System.',
                'email_subject': 'Account Invitation'
            }
        }
    
    async def validate_email_configuration(self) -> Dict[str, Any]:
        """
        Validate email configuration settings.
        
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_results = {
            'smtp_host': bool(self.smtp_host),
            'smtp_port': bool(self.smtp_port),
            'smtp_username': bool(self.smtp_username),
            'smtp_password': bool(self.smtp_password),
            'email_from': bool(self.email_from),
            'overall_valid': False
        }
        
        # Check if all required fields are present
        required_fields = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'email_from']
        validation_results['overall_valid'] = all(
            validation_results[field] for field in required_fields
        )
        
        return validation_results


# Global notification service instance
notification_service = NotificationService()
