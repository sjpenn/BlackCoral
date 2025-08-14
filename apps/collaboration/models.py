"""
BLACK CORAL Team Collaboration Models
Proposal teams, workflows, tasks, and real-time communication
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel

User = get_user_model()


class ProposalTeam(BaseModel):
    """
    Team assembled for a specific opportunity/proposal
    """
    TEAM_STATUS_CHOICES = [
        ('forming', 'Forming'),
        ('active', 'Active'),
        ('submitting', 'Submitting'),
        ('completed', 'Completed'),
        ('disbanded', 'Disbanded'),
    ]
    
    opportunity = models.OneToOneField(
        'opportunities.Opportunity', 
        on_delete=models.CASCADE, 
        related_name='proposal_team'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=TEAM_STATUS_CHOICES, default='forming')
    
    # Team leadership
    lead = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='led_teams')
    capture_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='captured_teams')
    proposal_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_teams')
    
    # Team configuration
    members = models.ManyToManyField(User, through='TeamMembership', related_name='proposal_teams')
    
    # Key dates
    kickoff_date = models.DateTimeField(null=True, blank=True)
    submission_deadline = models.DateTimeField(null=True, blank=True)
    
    # Team metrics
    total_hours_logged = models.FloatField(default=0.0)
    budget_allocated = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    budget_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['submission_deadline']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.opportunity.solicitation_number}"
    
    @property
    def days_until_deadline(self):
        """Calculate days until submission deadline"""
        if self.submission_deadline:
            delta = self.submission_deadline.date() - timezone.now().date()
            return delta.days
        return None
    
    @property
    def is_overdue(self):
        """Check if team is past deadline"""
        if self.submission_deadline:
            return timezone.now() > self.submission_deadline
        return False
    
    @property
    def budget_utilization(self):
        """Calculate budget utilization percentage"""
        if self.budget_allocated and self.budget_allocated > 0:
            return (self.budget_spent / self.budget_allocated) * 100
        return 0


class TeamMembership(BaseModel):
    """
    Team membership with roles and responsibilities
    """
    ROLE_CHOICES = [
        ('lead', 'Team Lead'),
        ('capture_manager', 'Capture Manager'),
        ('proposal_manager', 'Proposal Manager'),
        ('technical_lead', 'Technical Lead'),
        ('writer', 'Proposal Writer'),
        ('reviewer', 'Reviewer'),
        ('sme', 'Subject Matter Expert'),
        ('coordinator', 'Coordinator'),
        ('analyst', 'Analyst'),
        ('editor', 'Editor'),
        ('compliance', 'Compliance Specialist'),
        ('pricing', 'Pricing Analyst'),
    ]
    
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    responsibilities = models.TextField(blank=True)
    
    # Availability and commitment
    hours_committed = models.FloatField(default=0.0, help_text="Hours committed to this proposal")
    hours_logged = models.FloatField(default=0.0, help_text="Actual hours logged")
    availability_start = models.DateTimeField(null=True, blank=True)
    availability_end = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    tasks_assigned = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('team', 'user', 'role')
        ordering = ['role', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()} ({self.team.name})"
    
    @property
    def completion_rate(self):
        """Calculate task completion rate"""
        if self.tasks_assigned > 0:
            return (self.tasks_completed / self.tasks_assigned) * 100
        return 0
    
    @property
    def hours_variance(self):
        """Calculate variance between committed and logged hours"""
        return self.hours_logged - self.hours_committed


class ProposalSection(BaseModel):
    """
    Sections of a proposal with ownership and status tracking
    """
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('draft_complete', 'Draft Complete'),
        ('under_review', 'Under Review'),
        ('revision_needed', 'Revision Needed'),
        ('approved', 'Approved'),
        ('final', 'Final'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    section_number = models.CharField(max_length=20, help_text="e.g., 1.1, 2.3.1")
    
    # Ownership and assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_sections')
    reviewers = models.ManyToManyField(User, blank=True, related_name='sections_to_review')
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Content and requirements
    requirements = models.TextField(blank=True, help_text="Section requirements and guidelines")
    content = models.TextField(blank=True, help_text="Rich text content of the section")
    word_count_target = models.IntegerField(null=True, blank=True)
    word_count_current = models.IntegerField(default=0)
    
    # Collaboration tracking
    last_modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='last_modified_sections')
    last_modified_at = models.DateTimeField(null=True, blank=True)
    
    # Deadlines and tracking
    due_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # File attachments
    draft_file = models.FileField(upload_to='proposal_drafts/', null=True, blank=True)
    final_file = models.FileField(upload_to='proposal_sections/', null=True, blank=True)
    
    class Meta:
        ordering = ['section_number']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"{self.section_number} - {self.title}"
    
    @property
    def is_overdue(self):
        """Check if section is past due date"""
        if self.due_date and self.status not in ['approved', 'final']:
            return timezone.now() > self.due_date
        return False
    
    @property
    def days_until_due(self):
        """Calculate days until due date"""
        if self.due_date:
            delta = self.due_date.date() - timezone.now().date()
            return delta.days
        return None
    
    @property
    def word_count_progress(self):
        """Calculate word count progress percentage"""
        if self.word_count_target and self.word_count_target > 0:
            return min((self.word_count_current / self.word_count_target) * 100, 100)
        return 0


class TaskItem(BaseModel):
    """
    Individual tasks within proposal development
    """
    TASK_STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    TASK_TYPE_CHOICES = [
        ('research', 'Research'),
        ('writing', 'Writing'),
        ('review', 'Review'),
        ('coordination', 'Coordination'),
        ('analysis', 'Analysis'),
        ('compliance', 'Compliance Check'),
        ('editing', 'Editing'),
        ('formatting', 'Formatting'),
        ('meeting', 'Meeting'),
        ('other', 'Other'),
    ]
    
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE, related_name='tasks')
    section = models.ForeignKey(ProposalSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default='other')
    
    # Assignment and ownership
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    
    # Status and priority
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=10, choices=ProposalSection.PRIORITY_CHOICES, default='medium')
    
    # Time tracking
    estimated_hours = models.FloatField(default=0.0)
    actual_hours = models.FloatField(default=0.0)
    due_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Dependencies
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='blocking_tasks')
    
    # Progress tracking
    progress_percentage = models.IntegerField(default=0, help_text="Progress percentage (0-100)")
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-priority', 'due_date', 'created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['due_date']),
            models.Index(fields=['assigned_to']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def is_overdue(self):
        """Check if task is past due date"""
        if self.due_date and self.status != 'completed':
            return timezone.now() > self.due_date
        return False
    
    @property
    def hours_variance(self):
        """Calculate variance between estimated and actual hours"""
        return self.actual_hours - self.estimated_hours
    
    @property
    def can_start(self):
        """Check if task can start (all dependencies completed)"""
        return not self.depends_on.exclude(status='completed').exists()


class TeamComment(BaseModel):
    """
    Comments and discussions within proposal teams
    """
    COMMENT_TYPE_CHOICES = [
        ('general', 'General Discussion'),
        ('task', 'Task Comment'),
        ('section', 'Section Comment'),
        ('review', 'Review Comment'),
        ('decision', 'Decision Required'),
        ('update', 'Status Update'),
        ('issue', 'Issue/Problem'),
        ('solution', 'Solution/Resolution'),
    ]
    
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE, related_name='comments')
    
    # Context - what the comment is about
    task = models.ForeignKey(TaskItem, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    section = models.ForeignKey(ProposalSection, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    
    # Comment details
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_comments')
    comment_type = models.CharField(max_length=20, choices=COMMENT_TYPE_CHOICES, default='general')
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    
    # Threading and responses
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Mentions and notifications
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='mentioned_in_comments')
    
    # Status and resolution
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_comments')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True, help_text="File attachment references")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['team', '-created_at']),
            models.Index(fields=['comment_type']),
            models.Index(fields=['is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.author.get_full_name()}: {self.subject or self.content[:50]}..."
    
    @property
    def reply_count(self):
        """Count of replies to this comment"""
        return self.replies.count()


class TimeLog(BaseModel):
    """
    Time tracking for proposal team members
    """
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE, related_name='time_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_logs')
    
    # Time details
    date = models.DateField()
    hours = models.FloatField()
    description = models.TextField()
    
    # Context
    task = models.ForeignKey(TaskItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_logs')
    section = models.ForeignKey(ProposalSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_logs')
    
    # Approval workflow
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_time_logs')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['team', 'date']),
            models.Index(fields=['user', 'date']),
            models.Index(fields=['is_approved']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.hours}h on {self.date}"


class ProposalMilestone(BaseModel):
    """
    Key milestones in proposal development
    """
    MILESTONE_TYPE_CHOICES = [
        ('kickoff', 'Kickoff Meeting'),
        ('outline_complete', 'Outline Complete'),
        ('draft_complete', 'First Draft Complete'),
        ('review_complete', 'Review Complete'),
        ('final_draft', 'Final Draft Ready'),
        ('compliance_check', 'Compliance Check Complete'),
        ('final_review', 'Final Review Complete'),
        ('submission_ready', 'Ready for Submission'),
        ('submitted', 'Submitted'),
        ('award_notification', 'Award Notification'),
    ]
    
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE, related_name='milestones')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPE_CHOICES)
    
    # Dates and status
    target_date = models.DateTimeField()
    actual_date = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    
    # Ownership
    responsible_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Dependencies
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependent_milestones')
    
    class Meta:
        ordering = ['target_date']
        indexes = [
            models.Index(fields=['team', 'target_date']),
            models.Index(fields=['is_completed']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.target_date.date()}"
    
    @property
    def is_overdue(self):
        """Check if milestone is overdue"""
        if not self.is_completed and self.target_date:
            return timezone.now() > self.target_date
        return False
    
    @property
    def days_until_due(self):
        """Calculate days until target date"""
        if self.target_date:
            delta = self.target_date.date() - timezone.now().date()
            return delta.days
        return None


class SectionReview(BaseModel):
    """
    Section review assignments and tracking
    """
    REVIEW_STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    REVIEW_TYPE_CHOICES = [
        ('technical', 'Technical Review'),
        ('compliance', 'Compliance Review'),
        ('editorial', 'Editorial Review'),
        ('final', 'Final Review'),
        ('quality', 'Quality Assurance'),
    ]
    
    section = models.ForeignKey(ProposalSection, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_reviews')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_reviews_created')
    
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='assigned')
    
    # Deadlines
    due_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Review details
    instructions = models.TextField(blank=True, help_text="Specific review instructions")
    feedback = models.TextField(blank=True, help_text="Reviewer's feedback and comments")
    recommendation = models.CharField(
        max_length=20,
        choices=[
            ('approve', 'Approve'),
            ('approve_with_changes', 'Approve with Minor Changes'),
            ('reject', 'Reject - Major Revision Needed'),
            ('incomplete', 'Incomplete Review'),
        ],
        blank=True
    )
    
    # Ratings (1-5 scale)
    technical_accuracy = models.IntegerField(null=True, blank=True)
    clarity_score = models.IntegerField(null=True, blank=True)
    compliance_score = models.IntegerField(null=True, blank=True)
    overall_quality = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['section', 'status']),
            models.Index(fields=['reviewer', 'status']),
            models.Index(fields=['due_date']),
        ]
        unique_together = ['section', 'reviewer', 'review_type']
    
    def __str__(self):
        return f"{self.get_review_type_display()} - {self.section.title} by {self.reviewer.get_full_name()}"
    
    @property
    def is_overdue(self):
        """Check if review is overdue"""
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return timezone.now() > self.due_date
        return False
    
    @property
    def average_score(self):
        """Calculate average rating score"""
        scores = [s for s in [self.technical_accuracy, self.clarity_score, 
                             self.compliance_score, self.overall_quality] if s is not None]
        return sum(scores) / len(scores) if scores else None


class SectionApproval(BaseModel):
    """
    Section approval workflow tracking
    """
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('conditional', 'Conditionally Approved'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    APPROVAL_LEVEL_CHOICES = [
        ('technical_lead', 'Technical Lead'),
        ('proposal_manager', 'Proposal Manager'),
        ('team_lead', 'Team Lead'),
        ('quality_assurance', 'Quality Assurance'),
        ('compliance_officer', 'Compliance Officer'),
        ('final_authority', 'Final Authority'),
    ]
    
    section = models.ForeignKey(ProposalSection, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='section_approvals')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approval_requests')
    
    approval_level = models.CharField(max_length=20, choices=APPROVAL_LEVEL_CHOICES)
    status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    
    # Timing
    requested_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Approval details
    comments = models.TextField(blank=True, help_text="Approver's comments or conditions")
    conditions = models.TextField(blank=True, help_text="Conditions that must be met")
    priority = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='medium'
    )
    
    # Version tracking
    section_version = models.TextField(help_text="Content hash or version identifier")
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['section', 'status']),
            models.Index(fields=['approver', 'status']),
            models.Index(fields=['approval_level']),
            models.Index(fields=['due_date']),
        ]
        unique_together = ['section', 'approval_level']
    
    def __str__(self):
        return f"{self.get_approval_level_display()} approval for {self.section.title}"
    
    @property
    def is_overdue(self):
        """Check if approval is overdue"""
        if self.due_date and self.status == 'pending':
            return timezone.now() > self.due_date
        return False
    
    def approve(self, comments="", conditions=""):
        """Approve the section"""
        self.status = 'conditional' if conditions else 'approved'
        self.comments = comments
        self.conditions = conditions
        self.responded_at = timezone.now()
        self.save()
        
        # Update section status if this is the final approval
        if self.approval_level == 'final_authority' and self.status == 'approved':
            self.section.status = 'approved'
            self.section.save()
    
    def reject(self, comments=""):
        """Reject the section"""
        self.status = 'rejected'
        self.comments = comments
        self.responded_at = timezone.now()
        self.save()
        
        # Update section status
        self.section.status = 'revision_needed'
        self.section.save()


class WorkflowTemplate(BaseModel):
    """
    Predefined workflow templates for different section types
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    section_types = models.JSONField(default=list, help_text="Section types this template applies to")
    
    # Workflow configuration
    required_reviews = models.JSONField(default=list, help_text="Required review types")
    approval_sequence = models.JSONField(default=list, help_text="Ordered list of approval levels")
    auto_advance_conditions = models.JSONField(default=dict, help_text="Conditions for auto-advancing")
    
    # Timing defaults
    default_review_duration = models.IntegerField(default=3, help_text="Default review duration in days")
    default_approval_duration = models.IntegerField(default=2, help_text="Default approval duration in days")
    
    # Team and role requirements
    team = models.ForeignKey(ProposalTeam, on_delete=models.CASCADE, related_name='workflow_templates')
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['team', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.team.name}"
    
    def clean(self):
        """Validate workflow template"""
        if self.is_default:
            # Ensure only one default template per team
            existing_default = WorkflowTemplate.objects.filter(
                team=self.team, 
                is_default=True
            ).exclude(pk=self.pk)
            if existing_default.exists():
                raise ValidationError("Only one default workflow template allowed per team")


class SectionWorkflowInstance(BaseModel):
    """
    Tracks workflow progress for a specific section
    """
    WORKFLOW_STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_review', 'In Review'),
        ('in_approval', 'In Approval'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
        ('cancelled', 'Cancelled'),
    ]
    
    section = models.OneToOneField(ProposalSection, on_delete=models.CASCADE, related_name='workflow')
    template = models.ForeignKey(WorkflowTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=WORKFLOW_STATUS_CHOICES, default='not_started')
    current_step = models.CharField(max_length=50, blank=True)
    
    # Progress tracking
    steps_completed = models.JSONField(default=list)
    steps_pending = models.JSONField(default=list)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Workflow data
    metadata = models.JSONField(default=dict, help_text="Additional workflow data")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['current_step']),
        ]
    
    def __str__(self):
        return f"Workflow for {self.section.title}"
    
    @property
    def progress_percentage(self):
        """Calculate workflow completion percentage"""
        total_steps = len(self.steps_completed) + len(self.steps_pending)
        if total_steps == 0:
            return 0
        return (len(self.steps_completed) / total_steps) * 100
    
    def advance_workflow(self):
        """Advance to next workflow step"""
        if self.steps_pending:
            next_step = self.steps_pending.pop(0)
            self.steps_completed.append(self.current_step)
            self.current_step = next_step
            
            if not self.steps_pending:
                self.status = 'completed'
                self.completed_at = timezone.now()
            
            self.save()
            return True
        return False
    
    def get_current_requirements(self):
        """Get requirements for current workflow step"""
        if self.current_step == 'review':
            return self.section.reviews.filter(status__in=['assigned', 'in_progress'])
        elif self.current_step == 'approval':
            return self.section.approvals.filter(status='pending')
        return None