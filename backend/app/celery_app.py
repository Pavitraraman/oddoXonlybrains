"""
Celery application for background tasks in the Expense Management System.
Handles OCR processing, email notifications, exchange rate updates, and cleanup tasks.
"""

from celery import Celery
from celery.schedules import crontab
import logging

from config import settings

# Create Celery app
celery_app = Celery(
    'expense_management',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        'app.tasks.ocr_tasks',
        'app.tasks.notification_tasks',
        'app.tasks.currency_tasks',
        'app.tasks.cleanup_tasks'
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'update-exchange-rates': {
        'task': 'app.tasks.currency_tasks.update_exchange_rates',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
    'check-overdue-approvals': {
        'task': 'app.tasks.notification_tasks.check_overdue_approvals',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-old-notifications': {
        'task': 'app.tasks.cleanup_tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-audit-logs': {
        'task': 'app.tasks.cleanup_tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'backup-database': {
        'task': 'app.tasks.cleanup_tasks.backup_database',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    celery_app.start()

