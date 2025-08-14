from django.db import models
from apps.core.models import BaseModel


class AITask(BaseModel):
    """
    Track AI processing tasks and results.
    """
    TASK_TYPES = [
        ('analyze_opportunity', 'Analyze Opportunity'),
        ('compliance_check', 'Compliance Check'),
        ('generate_content', 'Generate Content'),
        ('summarize', 'Summarize Document'),
        ('draft', 'Draft Content'),
        ('quality', 'Quality Review'),
    ]
    
    AI_PROVIDERS = [
        ('claude', 'Claude (Anthropic)'),
        ('gemini', 'Google Gemini'),
        ('openrouter', 'OpenRouter'),
    ]
    
    task_type = models.CharField(max_length=30, choices=TASK_TYPES)
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE, null=True, blank=True)
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, null=True, blank=True)
    input_data = models.JSONField()
    output_data = models.JSONField(null=True, blank=True)
    ai_provider = models.CharField(max_length=20, choices=AI_PROVIDERS, default='claude')
    model_used = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True)
    tokens_used = models.IntegerField(null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_task_type_display()} - {self.status}"


class BidDecisionRecord(BaseModel):
    """
    Track bid/no-bid decisions for opportunities.
    """
    DECISION_CHOICES = [
        ('BID', 'Bid'),
        ('NO_BID', 'No Bid'),
        ('WATCH', 'Watch'),
    ]
    
    opportunity = models.OneToOneField('opportunities.Opportunity', on_delete=models.CASCADE, related_name='bid_decision')
    recommendation = models.CharField(max_length=10, choices=DECISION_CHOICES)
    overall_score = models.FloatField(help_text="Overall decision score (0-100)")
    confidence_score = models.FloatField(help_text="AI confidence in analysis (0.0-1.0)")
    
    # Decision factors (stored as individual fields for querying)
    strategic_alignment = models.FloatField()
    capability_match = models.FloatField()
    market_position = models.FloatField()
    estimated_value = models.FloatField()
    profit_potential = models.FloatField()
    resource_requirements = models.FloatField()
    technical_risk = models.FloatField()
    schedule_risk = models.FloatField()
    competitive_risk = models.FloatField()
    
    # Decision details
    rationale = models.TextField()
    key_strengths = models.JSONField(default=list)
    key_concerns = models.JSONField(default=list)
    action_items = models.JSONField(default=list)
    
    # Financial estimates
    estimated_bid_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    win_probability = models.FloatField(null=True, blank=True, help_text="Estimated win probability (0.0-1.0)")
    
    # Decision tracking
    decided_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True, blank=True)
    decision_date = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_decisions')
    review_date = models.DateTimeField(null=True, blank=True)
    
    # Actual outcome tracking
    actual_decision = models.CharField(max_length=10, choices=DECISION_CHOICES, blank=True, help_text="Final decision made")
    bid_submitted = models.BooleanField(default=False)
    contract_awarded = models.BooleanField(default=False)
    won_contract = models.BooleanField(default=False)
    actual_bid_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['-decision_date']
        indexes = [
            models.Index(fields=['recommendation']),
            models.Index(fields=['overall_score']),
            models.Index(fields=['decision_date']),
            models.Index(fields=['win_probability']),
        ]
    
    def __str__(self):
        return f"{self.opportunity.solicitation_number} - {self.recommendation} ({self.overall_score:.1f})"
    
    @property
    def score_category(self):
        """Categorize score for display"""
        if self.overall_score >= 80:
            return "Excellent"
        elif self.overall_score >= 70:
            return "Good"
        elif self.overall_score >= 50:
            return "Fair"
        else:
            return "Poor"
    
    @property
    def risk_level(self):
        """Calculate overall risk level"""
        avg_risk = (self.technical_risk + self.schedule_risk + self.competitive_risk) / 3
        if avg_risk >= 0.8:
            return "Low"
        elif avg_risk >= 0.6:
            return "Medium"
        else:
            return "High"