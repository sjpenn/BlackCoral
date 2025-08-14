from django.db import models
from apps.core.models import BaseModel


class Opportunity(BaseModel):
    """
    Government contracting opportunity from sam.gov and other sources.
    """
    # Basic Information
    title = models.CharField(max_length=500)
    solicitation_number = models.CharField(max_length=100, unique=True)
    agency = models.ForeignKey('core.Agency', on_delete=models.CASCADE, null=True, blank=True)
    naics_codes = models.ManyToManyField('core.NAICSCode', blank=True)
    description = models.TextField()
    
    # Dates
    posted_date = models.DateTimeField()
    response_date = models.DateTimeField(null=True, blank=True)
    award_date = models.DateTimeField(null=True, blank=True)
    archive_date = models.DateTimeField(null=True, blank=True)
    
    # Source Information
    source_url = models.URLField()
    source_api = models.CharField(max_length=50, default='sam.gov')
    
    # SAM.gov Specific Fields
    opportunity_type = models.CharField(max_length=50, blank=True)
    base_type = models.CharField(max_length=50, blank=True)
    archive_type = models.CharField(max_length=50, blank=True)
    set_aside_type = models.CharField(max_length=100, blank=True)
    classification_code = models.CharField(max_length=50, blank=True)
    
    # Location and Contact
    place_of_performance = models.JSONField(default=dict, blank=True)
    point_of_contact = models.JSONField(default=dict, blank=True)
    office_address = models.JSONField(default=dict, blank=True)
    
    # Award Information
    award_number = models.CharField(max_length=100, blank=True)
    award_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Additional Data
    raw_data = models.JSONField(default=dict, blank=True, help_text="Full API response data")
    resource_links = models.JSONField(default=list, blank=True)
    additional_info_link = models.URLField(blank=True)
    
    # Processing Status
    documents_fetched = models.BooleanField(default=False)
    ai_analysis_complete = models.BooleanField(default=False)
    compliance_checked = models.BooleanField(default=False)
    usaspending_analyzed = models.BooleanField(default=False)
    
    # USASpending.gov Analysis Results
    usaspending_data = models.JSONField(default=dict, blank=True, help_text="USASpending.gov analysis results")
    
    # AI Analysis Results
    ai_analysis_data = models.JSONField(default=dict, blank=True, help_text="AI-powered opportunity analysis")
    compliance_data = models.JSONField(default=dict, blank=True, help_text="AI compliance check results")
    generated_content = models.JSONField(default=dict, blank=True, help_text="AI-generated content (outlines, summaries)")
    
    class Meta:
        ordering = ['-posted_date']
        indexes = [
            models.Index(fields=['solicitation_number']),
            models.Index(fields=['posted_date']),
            models.Index(fields=['response_date']),
            models.Index(fields=['opportunity_type']),
            models.Index(fields=['set_aside_type']),
        ]
    
    def __str__(self):
        return f"{self.solicitation_number} - {self.title[:50]}"
    
    @property
    def is_open(self):
        """Check if opportunity is still open for responses."""
        if not self.response_date:
            return True
        from django.utils import timezone
        return self.response_date > timezone.now()
    
    @property
    def days_until_response(self):
        """Calculate days until response deadline."""
        if not self.response_date:
            return None
        from django.utils import timezone
        delta = self.response_date - timezone.now()
        return delta.days if delta.days > 0 else 0