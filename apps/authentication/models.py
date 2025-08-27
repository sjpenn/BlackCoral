from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import BaseModel


class User(AbstractUser):
    """
    Custom user model for BLACK CORAL with role-based access control.
    """
    
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        RESEARCHER = 'researcher', 'Researcher'
        REVIEWER = 'reviewer', 'Reviewer'
        COMPLIANCE_MONITOR = 'compliance_monitor', 'Compliance Monitor'
        QA = 'qa', 'Quality Assurance'
        SUBMISSION_AGENT = 'submission_agent', 'Submission Agent'
    
    # Fix related_name conflicts with default User model
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='blackcoral_users',
        related_query_name='blackcoral_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='blackcoral_users',
        related_query_name='blackcoral_user',
    )
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RESEARCHER,
        help_text="User's role in the BLACK CORAL system"
    )
    
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    security_clearance = models.CharField(max_length=50, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def can_manage_users(self):
        return self.role == self.Role.ADMIN
    
    @property
    def can_research_opportunities(self):
        return self.role in [self.Role.ADMIN, self.Role.RESEARCHER]
    
    @property
    def can_review_content(self):
        return self.role in [self.Role.ADMIN, self.Role.REVIEWER, self.Role.QA]
    
    @property
    def can_monitor_compliance(self):
        return self.role in [self.Role.ADMIN, self.Role.COMPLIANCE_MONITOR]
    
    @property
    def can_submit_proposals(self):
        return self.role in [self.Role.ADMIN, self.Role.SUBMISSION_AGENT]


class UserSession(BaseModel):
    """
    Track user sessions for audit and security purposes.
    """
    user = models.ForeignKey('authentication.User', on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


class UserPreferences(BaseModel):
    """
    User preferences and settings.
    """
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE, related_name='preferences')
    dashboard_layout = models.JSONField(default=dict)
    notification_settings = models.JSONField(default=dict)
    default_filters = models.JSONField(default=dict)
    
    class Meta:
        verbose_name_plural = "User Preferences"
    
    def __str__(self):
        return f"{self.user.username} preferences"