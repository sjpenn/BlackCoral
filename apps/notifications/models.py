"""
BLACK CORAL Real-Time Notification System
User notifications, alerts, and communication management
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from apps.core.models import BaseModel

User = get_user_model()


class NotificationPreference(BaseModel):
    """
    User preferences for different types of notifications
    """
    NOTIFICATION_TYPES = [
        ('opportunity_new', 'New Opportunity Available'),
        ('opportunity_deadline', 'Opportunity Deadline Approaching'),
        ('decision_made', 'Bid Decision Made'),
        ('team_assignment', 'Team Assignment'),
        ('task_assigned', 'Task Assigned'),
        ('task_due', 'Task Due Soon'),
        ('task_overdue', 'Task Overdue'),
        ('milestone_approaching', 'Milestone Approaching'),
        ('milestone_overdue', 'Milestone Overdue'),
        ('comment_mention', 'Mentioned in Comment'),
        ('comment_reply', 'Comment Reply'),
        ('review_request', 'Review Request'),
        ('proposal_submitted', 'Proposal Submitted'),
        ('award_notification', 'Award Notification'),
        ('system_update', 'System Update'),
    ]
    
    DELIVERY_METHODS = [
        ('in_app', 'In-App Notification'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('slack', 'Slack'),
        ('teams', 'Microsoft Teams'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_preferences')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHODS)
    is_enabled = models.BooleanField(default=True)
    
    # Timing preferences
    immediate = models.BooleanField(default=True)
    daily_digest = models.BooleanField(default=False)
    weekly_digest = models.BooleanField(default=False)
    
    # Quiet hours
    quiet_hours_start = models.TimeField(null=True, blank=True, help_text="Start of quiet hours (no notifications)")
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text="End of quiet hours")
    
    class Meta:
        unique_together = ('user', 'notification_type', 'delivery_method')
        indexes = [
            models.Index(fields=['user', 'notification_type']),
            models.Index(fields=['is_enabled']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_notification_type_display()} via {self.get_delivery_method_display()}"


class Notification(BaseModel):
    """
    Individual notification instances
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('dismissed', 'Dismissed'),
    ]
    
    # Recipient
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    # Notification details
    notification_type = models.CharField(max_length=30, choices=NotificationPreference.NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Delivery
    delivery_method = models.CharField(max_length=20, choices=NotificationPreference.DELIVERY_METHODS, default='in_app')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Context - what this notification is about
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Links and actions
    action_url = models.URLField(blank=True, null=True, help_text="URL to navigate to when notification is clicked")
    action_label = models.CharField(max_length=50, blank=True, null=True, help_text="Label for the action button")
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional notification data")
    
    # Timing
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text="When to send the notification")
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When notification expires")
    
    # Grouping (for digest notifications)
    group_key = models.CharField(max_length=100, blank=True, help_text="Key for grouping related notifications")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
            models.Index(fields=['scheduled_for']),
            models.Index(fields=['group_key']),
        ]
    
    def __str__(self):
        return f"{self.title} -> {self.user.get_full_name()}"
    
    @property
    def is_read(self):
        """Check if notification has been read"""
        return self.status == 'read'
    
    @property
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.status = 'read'
        self.read_at = timezone.now()
        self.save(update_fields=['status', 'read_at'])
    
    def mark_as_dismissed(self):
        """Mark notification as dismissed"""
        self.status = 'dismissed'
        self.save(update_fields=['status'])


class NotificationTemplate(BaseModel):
    """
    Templates for different types of notifications
    """
    notification_type = models.CharField(max_length=30, choices=NotificationPreference.NOTIFICATION_TYPES, unique=True)
    
    # Template content
    title_template = models.CharField(max_length=200, help_text="Title template with variables like {user_name}")
    message_template = models.TextField(help_text="Message template with variables")
    email_subject_template = models.CharField(max_length=200, blank=True)
    email_body_template = models.TextField(blank=True)
    
    # Default settings
    default_priority = models.CharField(max_length=10, choices=Notification.PRIORITY_CHOICES, default='medium')
    default_delivery_methods = models.JSONField(default=list, help_text="List of default delivery methods")
    
    # Template variables documentation
    available_variables = models.JSONField(default=list, help_text="List of available template variables")
    
    # Timing
    send_immediately = models.BooleanField(default=True)
    delay_minutes = models.IntegerField(default=0, help_text="Minutes to delay before sending")
    expires_after_hours = models.IntegerField(null=True, blank=True, help_text="Hours after which notification expires")
    
    class Meta:
        ordering = ['notification_type']
    
    def __str__(self):
        return f"Template: {self.get_notification_type_display()}"
    
    def render_title(self, context):
        """Render title template with context variables"""
        return self.title_template.format(**context)
    
    def render_message(self, context):
        """Render message template with context variables"""
        return self.message_template.format(**context)
    
    def render_email_subject(self, context):
        """Render email subject template with context variables"""
        if self.email_subject_template:
            return self.email_subject_template.format(**context)
        return self.render_title(context)
    
    def render_email_body(self, context):
        """Render email body template with context variables"""
        if self.email_body_template:
            return self.email_body_template.format(**context)
        return self.render_message(context)


class NotificationDigest(BaseModel):
    """
    Digest notifications that group multiple notifications
    """
    DIGEST_TYPE_CHOICES = [
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
        ('custom', 'Custom Digest'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_digests')
    digest_type = models.CharField(max_length=10, choices=DIGEST_TYPE_CHOICES)
    
    # Digest content
    title = models.CharField(max_length=200)
    summary = models.TextField()
    
    # Included notifications
    notifications = models.ManyToManyField(Notification, related_name='digests')
    notification_count = models.IntegerField(default=0)
    
    # Digest period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Delivery
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, choices=Notification.STATUS_CHOICES, default='pending')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'digest_type']),
            models.Index(fields=['period_start', 'period_end']),
        ]
    
    def __str__(self):
        return f"{self.get_digest_type_display()} for {self.user.get_full_name()} ({self.period_start.date()})"


class AlertRule(BaseModel):
    """
    Custom alert rules for automated notifications
    """
    TRIGGER_TYPES = [
        ('opportunity_deadline', 'Opportunity Deadline'),
        ('task_overdue', 'Task Overdue'),
        ('milestone_missed', 'Milestone Missed'),
        ('budget_threshold', 'Budget Threshold'),
        ('time_threshold', 'Time Threshold'),
        ('inactivity', 'Team Inactivity'),
        ('custom', 'Custom Rule'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPES)
    
    # Rule configuration
    is_active = models.BooleanField(default=True)
    conditions = models.JSONField(help_text="Rule conditions as JSON")
    
    # Notification settings
    notification_type = models.CharField(max_length=30, choices=NotificationPreference.NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=Notification.PRIORITY_CHOICES, default='medium')
    message_template = models.TextField()
    
    # Targeting
    target_users = models.ManyToManyField(User, blank=True, related_name='alert_rules')
    target_roles = models.JSONField(default=list, blank=True, help_text="List of roles to target")
    
    # Frequency control
    max_frequency_hours = models.IntegerField(default=24, help_text="Minimum hours between alerts")
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['trigger_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Alert Rule: {self.name}"
    
    def can_trigger(self):
        """Check if rule can trigger based on frequency limits"""
        if not self.is_active:
            return False
        
        if self.last_triggered:
            hours_since_last = (timezone.now() - self.last_triggered).total_seconds() / 3600
            return hours_since_last >= self.max_frequency_hours
        
        return True
    
    def trigger(self, context=None):
        """Trigger the alert rule"""
        if not self.can_trigger():
            return False
        
        # Update trigger tracking
        self.last_triggered = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=['last_triggered', 'trigger_count'])
        
        # TODO: Create notifications for target users
        return True


class WebhookEndpoint(BaseModel):
    """
    Webhook endpoints for external notification integrations
    """
    SERVICE_TYPES = [
        ('slack', 'Slack'),
        ('teams', 'Microsoft Teams'),
        ('discord', 'Discord'),
        ('webhook', 'Generic Webhook'),
        ('zapier', 'Zapier'),
        ('ifttt', 'IFTTT'),
    ]
    
    name = models.CharField(max_length=200)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    webhook_url = models.URLField()
    
    # Configuration
    is_active = models.BooleanField(default=True)
    headers = models.JSONField(default=dict, blank=True, help_text="Custom headers for webhook requests")
    payload_template = models.TextField(blank=True, help_text="JSON payload template")
    
    # Filtering
    notification_types = models.JSONField(default=list, help_text="List of notification types to send")
    priority_filter = models.JSONField(default=list, help_text="List of priorities to send")
    
    # Security
    secret_token = models.CharField(max_length=200, blank=True, help_text="Secret token for webhook verification")
    
    # Monitoring
    last_sent = models.DateTimeField(null=True, blank=True)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['service_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_service_type_display()})"
    
    @property
    def success_rate(self):
        """Calculate webhook success rate"""
        total = self.success_count + self.failure_count
        if total > 0:
            return (self.success_count / total) * 100
        return 0