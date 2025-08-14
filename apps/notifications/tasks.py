"""
BLACK CORAL Notification Tasks
Celery tasks for scheduled notification delivery and background processing
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

from .services import notification_service
from .signals import (
    check_overdue_tasks, 
    check_approaching_deadlines, 
    check_inactive_teams
)
from .models import Notification, NotificationDigest, AlertRule

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_pending_notifications(self):
    """Process and send pending notifications"""
    try:
        notification_service.send_immediate_notifications()
        logger.info("Processed pending notifications successfully")
        return {"status": "success", "message": "Pending notifications processed"}
    except Exception as exc:
        logger.error(f"Failed to process pending notifications: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def create_daily_digests(self):
    """Create daily digest notifications"""
    try:
        notification_service.create_digest_notifications('daily')
        logger.info("Created daily digest notifications successfully")
        return {"status": "success", "message": "Daily digests created"}
    except Exception as exc:
        logger.error(f"Failed to create daily digests: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def create_weekly_digests(self):
    """Create weekly digest notifications"""
    try:
        notification_service.create_digest_notifications('weekly')
        logger.info("Created weekly digest notifications successfully")
        return {"status": "success", "message": "Weekly digests created"}
    except Exception as exc:
        logger.error(f"Failed to create weekly digests: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def process_alert_rules(self):
    """Process and trigger alert rules"""
    try:
        notification_service.trigger_alert_rules()
        logger.info("Processed alert rules successfully")
        return {"status": "success", "message": "Alert rules processed"}
    except Exception as exc:
        logger.error(f"Failed to process alert rules: {exc}")
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=3)
def check_deadline_notifications(self):
    """Check for approaching deadlines and overdue items"""
    try:
        # Check for overdue tasks
        check_overdue_tasks()
        
        # Check for approaching deadlines
        check_approaching_deadlines()
        
        # Check for inactive teams
        check_inactive_teams()
        
        logger.info("Deadline check completed successfully")
        return {"status": "success", "message": "Deadline notifications checked"}
    except Exception as exc:
        logger.error(f"Failed to check deadlines: {exc}")
        raise self.retry(exc=exc, countdown=180)


@shared_task(bind=True, max_retries=3)
def cleanup_expired_notifications(self):
    """Clean up expired notifications"""
    try:
        # Delete expired notifications
        expired_count = Notification.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        # Delete old read notifications (older than 90 days)
        old_date = timezone.now() - timedelta(days=90)
        old_read_count = Notification.objects.filter(
            status='read',
            read_at__lt=old_date
        ).delete()[0]
        
        # Delete old dismissed notifications (older than 30 days)
        old_dismissed_count = Notification.objects.filter(
            status='dismissed',
            updated_at__lt=timezone.now() - timedelta(days=30)
        ).delete()[0]
        
        logger.info(f"Cleanup completed: {expired_count} expired, {old_read_count} old read, {old_dismissed_count} old dismissed")
        
        return {
            "status": "success",
            "expired": expired_count,
            "old_read": old_read_count,
            "old_dismissed": old_dismissed_count
        }
    except Exception as exc:
        logger.error(f"Failed to cleanup notifications: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, notification_id):
    """Send individual notification via email"""
    try:
        notification = Notification.objects.get(id=notification_id)
        success = notification_service._send_email_notification(notification)
        
        if success:
            logger.info(f"Email notification sent successfully: {notification_id}")
            return {"status": "success", "notification_id": notification_id}
        else:
            logger.warning(f"Email notification failed: {notification_id}")
            return {"status": "failed", "notification_id": notification_id}
            
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {"status": "error", "message": "Notification not found"}
    except Exception as exc:
        logger.error(f"Failed to send email notification {notification_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_webhook_notification(self, notification_id, service_type):
    """Send individual notification via webhook"""
    try:
        notification = Notification.objects.get(id=notification_id)
        success = notification_service._send_webhook_notification(notification, service_type)
        
        if success:
            logger.info(f"Webhook notification sent successfully: {notification_id} to {service_type}")
            return {"status": "success", "notification_id": notification_id, "service": service_type}
        else:
            logger.warning(f"Webhook notification failed: {notification_id} to {service_type}")
            return {"status": "failed", "notification_id": notification_id, "service": service_type}
            
    except Notification.DoesNotExist:
        logger.error(f"Notification not found: {notification_id}")
        return {"status": "error", "message": "Notification not found"}
    except Exception as exc:
        logger.error(f"Failed to send webhook notification {notification_id} to {service_type}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def batch_notification_delivery(self, notification_ids):
    """Deliver multiple notifications in batch"""
    try:
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            status='pending'
        )
        
        success_count = 0
        failure_count = 0
        
        for notification in notifications:
            try:
                notification_service._deliver_notification(notification)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to deliver notification {notification.id}: {e}")
                failure_count += 1
        
        logger.info(f"Batch delivery completed: {success_count} success, {failure_count} failures")
        
        return {
            "status": "completed",
            "success_count": success_count,
            "failure_count": failure_count,
            "total": len(notification_ids)
        }
        
    except Exception as exc:
        logger.error(f"Failed batch notification delivery: {exc}")
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=3)
def generate_notification_analytics(self):
    """Generate notification analytics and reports"""
    try:
        from django.db.models import Count, Q
        
        # Calculate analytics for the past 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        analytics = {
            'total_sent': Notification.objects.filter(
                created_at__gte=thirty_days_ago
            ).count(),
            'by_type': dict(
                Notification.objects.filter(
                    created_at__gte=thirty_days_ago
                ).values('notification_type').annotate(
                    count=Count('id')
                ).values_list('notification_type', 'count')
            ),
            'by_priority': dict(
                Notification.objects.filter(
                    created_at__gte=thirty_days_ago
                ).values('priority').annotate(
                    count=Count('id')
                ).values_list('priority', 'count')
            ),
            'delivery_status': dict(
                Notification.objects.filter(
                    created_at__gte=thirty_days_ago
                ).values('status').annotate(
                    count=Count('id')
                ).values_list('status', 'count')
            ),
            'read_rate': Notification.objects.filter(
                created_at__gte=thirty_days_ago,
                status='read'
            ).count() / max(1, Notification.objects.filter(
                created_at__gte=thirty_days_ago
            ).count()) * 100
        }
        
        # Store analytics in cache or database
        from django.core.cache import cache
        cache.set('notification_analytics', analytics, 86400)  # Cache for 24 hours
        
        logger.info("Notification analytics generated successfully")
        return {"status": "success", "analytics": analytics}
        
    except Exception as exc:
        logger.error(f"Failed to generate notification analytics: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def process_notification_templates(self):
    """Process and validate notification templates"""
    try:
        from .models import NotificationTemplate
        
        templates = NotificationTemplate.objects.all()
        processed_count = 0
        error_count = 0
        
        for template in templates:
            try:
                # Test template rendering with sample context
                test_context = {
                    'user_name': 'Test User',
                    'user_first_name': 'Test',
                    'user_email': 'test@example.com',
                    'object_title': 'Test Object',
                    'current_date': timezone.now().date(),
                    'current_time': timezone.now().time(),
                }
                
                # Try rendering templates
                template.render_title(test_context)
                template.render_message(test_context)
                
                if template.email_subject_template:
                    template.render_email_subject(test_context)
                
                if template.email_body_template:
                    template.render_email_body(test_context)
                
                processed_count += 1
                
            except Exception as e:
                logger.warning(f"Template validation failed for {template.notification_type}: {e}")
                error_count += 1
        
        logger.info(f"Template processing completed: {processed_count} valid, {error_count} errors")
        
        return {
            "status": "completed",
            "processed": processed_count,
            "errors": error_count
        }
        
    except Exception as exc:
        logger.error(f"Failed to process notification templates: {exc}")
        raise self.retry(exc=exc, countdown=300)


# Periodic task setup helpers
def setup_periodic_tasks():
    """Setup periodic notification tasks"""
    from celery.schedules import crontab
    from django.conf import settings
    
    # This would be called during app initialization
    periodic_tasks = {
        'process-pending-notifications': {
            'task': 'apps.notifications.tasks.process_pending_notifications',
            'schedule': 60.0,  # Every minute
        },
        'check-deadline-notifications': {
            'task': 'apps.notifications.tasks.check_deadline_notifications', 
            'schedule': crontab(hour='*', minute=0),  # Every hour
        },
        'create-daily-digests': {
            'task': 'apps.notifications.tasks.create_daily_digests',
            'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
        },
        'create-weekly-digests': {
            'task': 'apps.notifications.tasks.create_weekly_digests',
            'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday at 8 AM
        },
        'process-alert-rules': {
            'task': 'apps.notifications.tasks.process_alert_rules',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        },
        'cleanup-expired-notifications': {
            'task': 'apps.notifications.tasks.cleanup_expired_notifications',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        'generate-notification-analytics': {
            'task': 'apps.notifications.tasks.generate_notification_analytics',
            'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
        },
    }
    
    return periodic_tasks


logger.info("BLACK CORAL notification tasks registered")