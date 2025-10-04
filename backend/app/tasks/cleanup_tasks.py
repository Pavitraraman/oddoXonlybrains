"""
Cleanup and maintenance background tasks.
"""

import logging
import os
from datetime import datetime, timedelta
from app.celery_app import celery_app
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.cleanup_tasks.cleanup_old_notifications')
def cleanup_old_notifications(days_old: int = 30):
    """
    Clean up old notifications.
    
    Args:
        days_old: Delete notifications older than this many days
    """
    try:
        logger.info(f"Starting cleanup of notifications older than {days_old} days")
        
        async def cleanup():
            async with AsyncSessionLocal() as db:
                try:
                    deleted_count = await notification_service.delete_old_notifications(
                        days_old=days_old,
                        db=db
                    )
                    
                    logger.info(f"Cleaned up {deleted_count} old notifications")
                    return deleted_count
                    
                except Exception as e:
                    logger.error(f"Error cleaning up notifications: {e}")
                    raise
        
        # Run async function
        import asyncio
        deleted_count = asyncio.run(cleanup())
        
        logger.info(f"Notification cleanup completed. {deleted_count} notifications deleted.")
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'days_old': days_old
        }
        
    except Exception as e:
        logger.error(f"Notification cleanup failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.cleanup_tasks.cleanup_old_audit_logs')
def cleanup_old_audit_logs(days_old: int = 365):
    """
    Clean up old audit logs.
    
    Args:
        days_old: Delete audit logs older than this many days
    """
    try:
        logger.info(f"Starting cleanup of audit logs older than {days_old} days")
        
        async def cleanup():
            async with AsyncSessionLocal() as db:
                try:
                    deleted_count = await audit_service.cleanup_old_logs(
                        db=db,
                        days_old=days_old
                    )
                    
                    logger.info(f"Cleaned up {deleted_count} old audit logs")
                    return deleted_count
                    
                except Exception as e:
                    logger.error(f"Error cleaning up audit logs: {e}")
                    raise
        
        # Run async function
        import asyncio
        deleted_count = asyncio.run(cleanup())
        
        logger.info(f"Audit log cleanup completed. {deleted_count} audit logs deleted.")
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'days_old': days_old
        }
        
    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.cleanup_tasks.cleanup_old_files')
def cleanup_old_files(days_old: int = 90):
    """
    Clean up old uploaded files.
    
    Args:
        days_old: Delete files older than this many days
    """
    try:
        logger.info(f"Starting cleanup of files older than {days_old} days")
        
        from config import settings
        import glob
        from pathlib import Path
        
        upload_dir = Path(settings.upload_dir)
        if not upload_dir.exists():
            logger.warning(f"Upload directory {upload_dir} does not exist")
            return {
                'status': 'warning',
                'message': 'Upload directory does not exist',
                'deleted_count': 0
            }
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0
        
        # Find and delete old files
        for file_path in upload_dir.glob('*'):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file_path}: {e}")
        
        logger.info(f"File cleanup completed. {deleted_count} files deleted.")
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'days_old': days_old
        }
        
    except Exception as e:
        logger.error(f"File cleanup failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.cleanup_tasks.backup_database')
def backup_database():
    """
    Create database backup.
    """
    try:
        logger.info("Starting database backup")
        
        from config import settings
        import subprocess
        from datetime import datetime
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"expense_management_backup_{timestamp}.sql"
        backup_path = f"/tmp/{backup_filename}"
        
        # Database connection parameters
        db_host = settings.database_host
        db_port = settings.database_port
        db_name = settings.database_name
        db_user = settings.database_user
        db_password = settings.database_password
        
        # Create backup command
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        backup_cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', str(db_port),
            '-U', db_user,
            '-d', db_name,
            '-f', backup_path,
            '--verbose'
        ]
        
        # Execute backup
        result = subprocess.run(backup_cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Get backup file size
            backup_size = os.path.getsize(backup_path) if os.path.exists(backup_path) else 0
            
            logger.info(f"Database backup completed successfully. Size: {backup_size} bytes")
            
            # Optionally, you could upload the backup to cloud storage here
            
            return {
                'status': 'success',
                'backup_filename': backup_filename,
                'backup_size': backup_size,
                'backup_path': backup_path
            }
        else:
            logger.error(f"Database backup failed: {result.stderr}")
            return {
                'status': 'error',
                'message': result.stderr
            }
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.cleanup_tasks.optimize_database')
def optimize_database():
    """
    Optimize database performance.
    """
    try:
        logger.info("Starting database optimization")
        
        async def optimize():
            async with AsyncSessionLocal() as db:
                try:
                    from sqlalchemy import text
                    
                    # Update table statistics
                    await db.execute(text("ANALYZE"))
                    
                    # Reindex tables
                    await db.execute(text("REINDEX DATABASE expense_management"))
                    
                    # Vacuum database
                    await db.execute(text("VACUUM ANALYZE"))
                    
                    await db.commit()
                    
                    logger.info("Database optimization completed")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error optimizing database: {e}")
                    await db.rollback()
                    raise
        
        # Run async function
        import asyncio
        success = asyncio.run(optimize())
        
        if success:
            logger.info("Database optimization completed successfully")
            return {
                'status': 'success',
                'message': 'Database optimization completed'
            }
        else:
            return {
                'status': 'error',
                'message': 'Database optimization failed'
            }
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name='app.tasks.cleanup_tasks.generate_system_report')
def generate_system_report():
    """
    Generate system health and performance report.
    """
    try:
        logger.info("Generating system report")
        
        async def generate_report():
            async with AsyncSessionLocal() as db:
                try:
                    from sqlalchemy import select, func, text
                    from app.models import User, Expense, Approval, Notification, AuditLog
                    from datetime import datetime, timedelta
                    
                    # Get system statistics
                    stats = {}
                    
                    # User statistics
                    user_result = await db.execute(
                        select(func.count(User.id)).where(User.is_active == True)
                    )
                    stats['active_users'] = user_result.scalar()
                    
                    # Expense statistics
                    expense_result = await db.execute(
                        select(func.count(Expense.id), func.sum(Expense.amount_in_base_currency))
                        .where(Expense.created_at >= datetime.utcnow() - timedelta(days=30))
                    )
                    expense_count, expense_total = expense_result.scalar_one()
                    stats['expenses_last_30_days'] = expense_count or 0
                    stats['expense_total_last_30_days'] = float(expense_total or 0)
                    
                    # Pending approvals
                    pending_result = await db.execute(
                        select(func.count(Approval.id)).where(Approval.status == 'pending')
                    )
                    stats['pending_approvals'] = pending_result.scalar()
                    
                    # Unread notifications
                    notification_result = await db.execute(
                        select(func.count(Notification.id)).where(Notification.is_read == False)
                    )
                    stats['unread_notifications'] = notification_result.scalar()
                    
                    # Database size
                    size_result = await db.execute(text("""
                        SELECT pg_size_pretty(pg_database_size('expense_management'))
                    """))
                    stats['database_size'] = size_result.scalar()
                    
                    logger.info(f"System report generated: {stats}")
                    return stats
                    
                except Exception as e:
                    logger.error(f"Error generating system report: {e}")
                    raise
        
        # Run async function
        import asyncio
        stats = asyncio.run(generate_report())
        
        logger.info("System report generation completed")
        return {
            'status': 'success',
            'report': stats,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"System report generation failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }

