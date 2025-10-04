"""
Notification background tasks for email and system notifications.
"""

import logging
from app.celery_app import celery_app
from app.services.notification_service import notification_service
from app.services.approval_service import approval_service
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.notification_tasks.send_email_notification')
def send_email_notification(user_id: str, subject: str, message: str, html_content: str = None):
    """
    Send email notification to user.
    
    Args:
        user_id: ID of the user to notify
        subject: Email subject
        message: Email message
        html_content: Optional HTML content
    """
    try:
        logger.info(f"Sending email notification to user {user_id}")
        
        async def send_email():
            async with AsyncSessionLocal() as db:
                try:
                    success = await notification_service.send_email_notification(
                        user_id=user_id,
                        subject=subject,
                        message=message,
                        html_content=html_content,
                        db=db
                    )
                    
                    if success:
                        logger.info(f"Email notification sent to user {user_id}")
                    else:
                        logger.warning(f"Failed to send email notification to user {user_id}")
                    
                    return success
                    
                except Exception as e:
                    logger.error(f"Error sending email notification: {e}")
                    raise
        
        # Run async function
        import asyncio
        success = asyncio.run(send_email())
        
        return {
            'status': 'success' if success else 'failed',
            'user_id': user_id,
            'subject': subject
        }
        
    except Exception as e:
        logger.error(f"Email notification task failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'user_id': user_id
        }


@celery_app.task(name='app.tasks.notification_tasks.send_bulk_notifications')
def send_bulk_notifications(notifications: list):
    """
    Send multiple notifications in batch.
    
    Args:
        notifications: List of notification dictionaries
    """
    try:
        logger.info(f"Sending {len(notifications)} bulk notifications")
        
        results = []
        for notification in notifications:
            try:
                result = send_email_notification.delay(
                    user_id=notification['user_id'],
                    subject=notification['subject'],
                    message=notification['message'],
                    html_content=notification.get('html_content')
                )
                results.append(result.get(timeout=60))  # 1 minute timeout per email
            except Exception as e:
                logger.error(f"Error sending notification to {notification['user_id']}: {e}")
                results.append({'status': 'error', 'message': str(e)})
        
        success_count = sum(1 for r in results if r.get('status') == 'success')
        logger.info(f"Bulk notification sending completed. {success_count}/{len(notifications)} sent successfully.")
        
        return {
            'status': 'completed',
            'total': len(notifications),
            'successful': success_count,
            'failed': len(notifications) - success_count,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Bulk notification task failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.notification_tasks.check_overdue_approvals')
def check_overdue_approvals():
    """
    Check for overdue approvals and send notifications.
    """
    try:
        logger.info("Checking for overdue approvals")
        
        async def check_overdue():
            async with AsyncSessionLocal() as db:
                try:
                    overdue_approvals = await approval_service.check_overdue_approvals(db)
                    
                    if overdue_approvals:
                        logger.info(f"Found {len(overdue_approvals)} overdue approvals")
                        
                        # Send notifications for each overdue approval
                        for approval in overdue_approvals:
                            await notification_service.create_notification(
                                user_id=str(approval.approver_id),
                                type="overdue_approval",
                                title="Overdue Approval Required",
                                message=f"Expense '{approval.expense.description}' approval is overdue",
                                metadata={
                                    "expense_id": str(approval.expense.id),
                                    "days_overdue": (approval.created_at - approval.created_at).days
                                },
                                db=db
                            )
                    
                    return len(overdue_approvals)
                    
                except Exception as e:
                    logger.error(f"Error checking overdue approvals: {e}")
                    raise
        
        # Run async function
        import asyncio
        overdue_count = asyncio.run(check_overdue())
        
        logger.info(f"Overdue approval check completed. {overdue_count} overdue approvals found.")
        return {
            'status': 'success',
            'overdue_count': overdue_count
        }
        
    except Exception as e:
        logger.error(f"Overdue approval check failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.notification_tasks.send_weekly_reports')
def send_weekly_reports():
    """
    Send weekly expense reports to managers and admins.
    """
    try:
        logger.info("Sending weekly expense reports")
        
        async def send_reports():
            async with AsyncSessionLocal() as db:
                try:
                    from sqlalchemy import select
                    from app.models import User, UserRole
                    
                    # Get all managers and admins
                    result = await db.execute(
                        select(User).where(
                            User.role.in_([UserRole.manager, UserRole.admin]),
                            User.is_active == True
                        )
                    )
                    users = result.scalars().all()
                    
                    # Send reports to each user
                    for user in users:
                        # Generate weekly report data
                        report_data = await generate_weekly_report(user, db)
                        
                        # Create notification
                        await notification_service.create_notification(
                            user_id=str(user.id),
                            type="weekly_report",
                            title="Weekly Expense Report",
                            message=f"Your weekly expense report is ready. Total expenses: ${report_data.get('total_expenses', 0)}",
                            metadata=report_data,
                            db=db
                        )
                    
                    logger.info(f"Weekly reports sent to {len(users)} users")
                    return len(users)
                    
                except Exception as e:
                    logger.error(f"Error sending weekly reports: {e}")
                    raise
        
        # Run async function
        import asyncio
        sent_count = asyncio.run(send_reports())
        
        logger.info(f"Weekly report sending completed. {sent_count} reports sent.")
        return {
            'status': 'success',
            'reports_sent': sent_count
        }
        
    except Exception as e:
        logger.error(f"Weekly report sending failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


async def generate_weekly_report(user, db):
    """Generate weekly report data for a user."""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import select, func
        from app.models import Expense, Approval
        
        # Get date range for last week
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=7)
        
        if user.role == UserRole.admin:
            # Admin gets company-wide stats
            result = await db.execute(
                select(func.count(Expense.id), func.sum(Expense.amount_in_base_currency))
                .where(
                    Expense.company_id == user.company_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )
            total_expenses, total_amount = result.scalar_one()
            
        elif user.role == UserRole.manager:
            # Manager gets team stats
            result = await db.execute(
                select(func.count(Approval.id))
                .where(
                    Approval.approver_id == user.id,
                    Approval.created_at >= start_date,
                    Approval.created_at <= end_date
                )
            )
            approvals_count = result.scalar()
            
            total_expenses = approvals_count
            total_amount = 0  # Calculate based on approvals
        
        else:
            # Employee gets personal stats
            result = await db.execute(
                select(func.count(Expense.id), func.sum(Expense.amount_in_base_currency))
                .where(
                    Expense.user_id == user.id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )
            total_expenses, total_amount = result.scalar_one()
        
        return {
            'total_expenses': total_expenses or 0,
            'total_amount': float(total_amount or 0),
            'period': f"{start_date} to {end_date}",
            'user_role': user.role.value
        }
        
    except Exception as e:
        logger.error(f"Error generating weekly report: {e}")
        return {
            'total_expenses': 0,
            'total_amount': 0,
            'period': 'Unknown',
            'user_role': user.role.value if user else 'unknown'
        }

