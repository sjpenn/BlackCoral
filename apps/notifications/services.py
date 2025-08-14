"""
BLACK CORAL Notification Service
Real-time notification creation, delivery, and management
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.conf import settings
from django.template import Template, Context

from .models import (
    Notification, NotificationPreference, NotificationTemplate,
    NotificationDigest, AlertRule, WebhookEndpoint
)

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Central service for managing notifications"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.NotificationService")
    
    def create_notification(self, 
                          user: User,
                          notification_type: str,
                          title: str = None,
                          message: str = None,
                          priority: str = 'medium',
                          content_object: Any = None,
                          action_url: str = None,
                          action_label: str = None,
                          metadata: Dict[str, Any] = None,
                          scheduled_for: datetime = None,
                          expires_after_hours: int = None) -> Notification:
        """
        Create a new notification for a user
        """
        
        # Get template if title/message not provided
        if not title or not message:
            template = self._get_template(notification_type)
            if template:
                context = self._build_context(user, content_object, metadata or {})
                title = title or template.render_title(context)
                message = message or template.render_message(context)
                if not expires_after_hours and template.expires_after_hours:
                    expires_after_hours = template.expires_after_hours
        
        # Calculate expiration
        expires_at = None
        if expires_after_hours:
            expires_at = timezone.now() + timedelta(hours=expires_after_hours)
        
        # Create content type reference if content_object provided
        content_type = None
        object_id = None
        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.pk
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            content_type=content_type,
            object_id=object_id,
            action_url=action_url,
            action_label=action_label,
            metadata=metadata or {},
            scheduled_for=scheduled_for,
            expires_at=expires_at
        )
        
        self.logger.info(f"Created notification {notification.id} for {user.get_full_name()}")
        
        # Schedule delivery
        self._schedule_delivery(notification)
        
        return notification
    
    def notify_multiple_users(self,
                            users: List[User],
                            notification_type: str,
                            title: str = None,
                            message: str = None,
                            **kwargs) -> List[Notification]:
        """
        Create notifications for multiple users
        """
        notifications = []
        for user in users:
            notification = self.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                **kwargs
            )
            notifications.append(notification)
        
        return notifications
    
    def notify_team_members(self,
                          team,
                          notification_type: str,
                          exclude_user: User = None,
                          roles: List[str] = None,
                          **kwargs) -> List[Notification]:
        """
        Notify team members with optional role filtering
        """
        # Get team members
        memberships = team.teammembership_set.filter(is_active=True)
        
        if roles:
            memberships = memberships.filter(role__in=roles)
        
        users = [m.user for m in memberships]
        
        if exclude_user:
            users = [u for u in users if u != exclude_user]
        
        return self.notify_multiple_users(users, notification_type, **kwargs)
    
    def send_immediate_notifications(self):
        """
        Send all pending immediate notifications
        """
        pending_notifications = Notification.objects.filter(
            status='pending',
            scheduled_for__lte=timezone.now()
        ).exclude(
            expires_at__lt=timezone.now()
        )
        
        for notification in pending_notifications:
            self._deliver_notification(notification)
    
    def create_digest_notifications(self, digest_type: str = 'daily'):
        """
        Create digest notifications for users who have them enabled
        """
        # Get users who want digest notifications
        users_wanting_digest = User.objects.filter(
            notification_preferences__daily_digest=True if digest_type == 'daily' else False,
            notification_preferences__weekly_digest=True if digest_type == 'weekly' else False
        ).distinct()
        
        for user in users_wanting_digest:
            self._create_user_digest(user, digest_type)
    
    def trigger_alert_rules(self):
        """
        Check and trigger alert rules
        """
        active_rules = AlertRule.objects.filter(is_active=True)
        
        for rule in active_rules:
            if rule.can_trigger():
                self._evaluate_alert_rule(rule)
    
    def mark_notification_read(self, notification_id: int, user: User) -> bool:
        """
        Mark a notification as read
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
    
    def mark_all_read(self, user: User, notification_type: str = None) -> int:
        """
        Mark all notifications as read for a user
        """
        queryset = Notification.objects.filter(user=user, status='sent')
        
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        count = queryset.update(status='read', read_at=timezone.now())
        return count
    
    def get_user_notifications(self, 
                             user: User,
                             unread_only: bool = False,
                             notification_type: str = None,
                             limit: int = 50) -> List[Notification]:
        """
        Get notifications for a user
        """
        queryset = Notification.objects.filter(user=user)
        
        if unread_only:
            queryset = queryset.exclude(status='read')
        
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Exclude expired notifications
        queryset = queryset.exclude(
            expires_at__lt=timezone.now()
        )
        
        return list(queryset.order_by('-created_at')[:limit])
    
    def get_unread_count(self, user: User) -> int:
        """
        Get count of unread notifications for a user
        """
        return Notification.objects.filter(
            user=user,
            status='sent'
        ).exclude(
            expires_at__lt=timezone.now()
        ).count()
    
    def _get_template(self, notification_type: str) -> Optional[NotificationTemplate]:
        """Get notification template for type"""
        try:
            return NotificationTemplate.objects.get(notification_type=notification_type)
        except NotificationTemplate.DoesNotExist:
            return None
    
    def _build_context(self, user: User, content_object: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build template context"""
        context = {
            'user_name': user.get_full_name(),
            'user_first_name': user.first_name,
            'user_email': user.email,
            'site_url': getattr(settings, 'SITE_URL', 'https://blackcoral.ai'),
            'current_date': timezone.now().date(),
            'current_time': timezone.now().time(),
        }
        
        # Add content object context
        if content_object:
            context['object'] = content_object
            if hasattr(content_object, 'title'):
                context['object_title'] = content_object.title
            if hasattr(content_object, 'name'):
                context['object_name'] = content_object.name
        
        # Add metadata
        context.update(metadata)
        
        return context
    
    def _schedule_delivery(self, notification: Notification):
        """Schedule notification delivery"""
        # Check user preferences
        preferences = NotificationPreference.objects.filter(
            user=notification.user,
            notification_type=notification.notification_type,
            is_enabled=True
        )
        
        # If immediate delivery preferred and no scheduling
        if not notification.scheduled_for:
            immediate_prefs = preferences.filter(immediate=True)
            if immediate_prefs.exists():
                self._deliver_notification(notification)
            else:
                # Schedule for later based on digest preferences
                notification.scheduled_for = timezone.now() + timedelta(minutes=5)
                notification.save()
    
    def _deliver_notification(self, notification: Notification):
        """Deliver notification via configured methods"""
        try:
            # Get user preferences for this notification type
            preferences = NotificationPreference.objects.filter(
                user=notification.user,
                notification_type=notification.notification_type,
                is_enabled=True
            )
            
            delivery_successful = False
            
            for preference in preferences:
                if preference.delivery_method == 'in_app':
                    # In-app notifications are created by default
                    delivery_successful = True
                elif preference.delivery_method == 'email':
                    delivery_successful = self._send_email_notification(notification)
                elif preference.delivery_method == 'slack':
                    delivery_successful = self._send_webhook_notification(notification, 'slack')
                elif preference.delivery_method == 'teams':
                    delivery_successful = self._send_webhook_notification(notification, 'teams')
            
            # Update notification status
            if delivery_successful:
                notification.status = 'sent'
                notification.sent_at = timezone.now()
            else:
                notification.status = 'failed'
            
            notification.save()
            
        except Exception as e:
            self.logger.error(f"Failed to deliver notification {notification.id}: {e}")
            notification.status = 'failed'
            notification.save()
    
    def _send_email_notification(self, notification: Notification) -> bool:
        """Send notification via email"""
        try:
            template = self._get_template(notification.notification_type)
            context = self._build_context(notification.user, notification.content_object, notification.metadata)
            
            subject = notification.title
            if template:
                subject = template.render_email_subject(context)
            
            message = notification.message
            if template and template.email_body_template:
                message = template.render_email_body(context)
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@blackcoral.ai'),
                recipient_list=[notification.user.email],
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
            return False
    
    def _send_webhook_notification(self, notification: Notification, service_type: str) -> bool:
        """Send notification via webhook"""
        try:
            endpoints = WebhookEndpoint.objects.filter(
                service_type=service_type,
                is_active=True,
                notification_types__contains=[notification.notification_type]
            )
            
            for endpoint in endpoints:
                # TODO: Implement webhook delivery
                pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook notification: {e}")
            return False
    
    def _create_user_digest(self, user: User, digest_type: str):
        """Create digest notification for user"""
        # Determine digest period
        now = timezone.now()
        if digest_type == 'daily':
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif digest_type == 'weekly':
            days_since_monday = now.weekday()
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday + 7)
            period_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        else:
            return
        
        # Get notifications for digest
        notifications = Notification.objects.filter(
            user=user,
            created_at__gte=period_start,
            created_at__lt=period_end,
            status='sent'
        ).exclude(
            notification_type__in=['system_update']  # Exclude certain types from digest
        )
        
        if notifications.count() == 0:
            return
        
        # Create digest
        digest = NotificationDigest.objects.create(
            user=user,
            digest_type=digest_type,
            title=f"{digest_type.title()} Digest - {period_start.date()}",
            summary=f"You have {notifications.count()} updates from your BLACK CORAL activities.",
            period_start=period_start,
            period_end=period_end,
            notification_count=notifications.count()
        )
        
        digest.notifications.set(notifications)
        
        # Send digest notification
        self.create_notification(
            user=user,
            notification_type='system_update',
            title=digest.title,
            message=digest.summary,
            priority='low',
            content_object=digest
        )
    
    def _evaluate_alert_rule(self, rule: AlertRule):
        """Evaluate and potentially trigger an alert rule"""
        # TODO: Implement alert rule evaluation logic
        # This would check the rule conditions against current system state
        pass


# Global notification service instance
notification_service = NotificationService()


# Convenience functions
def create_notification(**kwargs):
    """Convenience function to create a notification"""
    return notification_service.create_notification(**kwargs)


def notify_team_members(**kwargs):
    """Convenience function to notify team members"""
    return notification_service.notify_team_members(**kwargs)


def notify_multiple_users(**kwargs):
    """Convenience function to notify multiple users"""
    return notification_service.notify_multiple_users(**kwargs)