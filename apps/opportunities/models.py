from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel

User = get_user_model()


class Opportunity(BaseModel):
    """
    Government contracting opportunity from sam.gov and other sources.
    """
    # Basic Information
    title = models.CharField(max_length=500)
    solicitation_number = models.CharField(max_length=100, unique=True)
    notice_id = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="SAM.gov notice ID (noticeId)")
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
    metadata = models.JSONField(default=dict, blank=True, help_text="Agent OS workflow and processing metadata")
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
            models.Index(fields=['notice_id']),
            models.Index(fields=['posted_date']),
            models.Index(fields=['response_date']),
            models.Index(fields=['opportunity_type']),
            models.Index(fields=['set_aside_type']),
            # JSONField index for workflow lookups
            models.Index(fields=['metadata'], name='opp_metadata_idx'),
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
    
    def get_workflow_id(self):
        """Get the Agent OS workflow ID for this opportunity."""
        return self.metadata.get('agent_os_workflow_id')
    
    def set_workflow_id(self, workflow_id):
        """Set the Agent OS workflow ID for this opportunity."""
        self.metadata['agent_os_workflow_id'] = workflow_id
        self.save(update_fields=['metadata'])
    
    def is_workflow_processed(self):
        """Check if Agent OS workflow has been processed."""
        return self.metadata.get('agent_os_workflow_processed', False)
    
    def mark_workflow_processed(self):
        """Mark the opportunity as processed by Agent OS workflow."""
        from django.utils import timezone
        self.metadata['agent_os_workflow_processed'] = True
        self.metadata['agent_os_workflow_processed_at'] = timezone.now().isoformat()
        self.save(update_fields=['metadata'])


class SearchCriteria(BaseModel):
    """
    Saved search criteria for SAM.gov opportunity searches.
    Allows users to save and reuse their search parameters.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=100, help_text="User-friendly name for this search")
    
    # Search parameters
    search_term = models.CharField(max_length=200, blank=True, help_text="Title/keyword search term")
    naics_codes = models.JSONField(default=list, blank=True, help_text="List of NAICS codes to search")
    agencies = models.JSONField(default=list, blank=True, help_text="List of agencies to search") 
    days_back = models.IntegerField(default=30, help_text="Number of days back to search")
    
    # User preferences
    is_favorite = models.BooleanField(default=False, help_text="Mark as favorite for quick access")
    last_used = models.DateTimeField(auto_now=True, help_text="Last time this search was used")
    
    class Meta:
        ordering = ['-last_used', '-is_favorite', 'name']
        indexes = [
            models.Index(fields=['user', 'is_favorite']),
            models.Index(fields=['user', 'last_used']),
        ]
        unique_together = ['user', 'name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"
    
    @property
    def search_summary(self):
        """Generate a human-readable summary of search parameters."""
        parts = []
        if self.search_term:
            parts.append(f"Title: '{self.search_term}'")
        if self.naics_codes:
            parts.append(f"NAICS: {', '.join(self.naics_codes)}")
        if self.agencies:
            parts.append(f"Agencies: {', '.join(self.agencies)}")
        parts.append(f"Last {self.days_back} days")
        return " | ".join(parts)


class OpportunityDocument(BaseModel):
    """
    Document tracking for opportunities with viewing history and metadata.
    Enhanced document management for the AGENT analysis pipeline.
    """
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='opportunity_documents')
    
    # Document Information
    url = models.URLField(help_text="Original document URL")
    name = models.CharField(max_length=500, help_text="Document name/title")
    document_type = models.CharField(max_length=50, choices=[
        ('resource', 'Resource Document'),
        ('additional_info', 'Additional Information'),
        ('web_link', 'Web Link'),
        ('solicitation', 'Solicitation Document'),
        ('amendment', 'Amendment'),
        ('attachment', 'Attachment'),
    ], default='resource')
    
    # File Metadata
    file_extension = models.CharField(max_length=20, blank=True, help_text="File extension (.pdf, .docx, etc.)")
    file_size_bytes = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True, help_text="MIME type")
    
    # Content Processing Status
    content_extracted = models.BooleanField(default=False, help_text="Text content has been extracted")
    extraction_status = models.CharField(max_length=50, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ], default='pending')
    
    # Extracted Content
    extracted_text = models.TextField(blank=True, help_text="Extracted text content")
    extraction_metadata = models.JSONField(default=dict, blank=True, help_text="Extraction process metadata")
    langextract_data = models.JSONField(default=dict, blank=True, help_text="LangExtract structured data")
    
    # Agent Analysis Status
    agent_analysis_status = models.CharField(max_length=50, choices=[
        ('not_started', 'Not Started'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='not_started')
    agent_analysis_data = models.JSONField(default=dict, blank=True, help_text="Agent analysis results")
    
    # Processing Timestamps
    first_viewed_at = models.DateTimeField(null=True, blank=True, help_text="First time document was viewed")
    last_viewed_at = models.DateTimeField(null=True, blank=True, help_text="Last time document was viewed")
    content_extracted_at = models.DateTimeField(null=True, blank=True, help_text="When content extraction completed")
    agent_analysis_completed_at = models.DateTimeField(null=True, blank=True, help_text="When agent analysis completed")
    
    # Usage Statistics
    view_count = models.IntegerField(default=0, help_text="Number of times document has been viewed")
    download_count = models.IntegerField(default=0, help_text="Number of times document has been downloaded")
    
    # Data Quality and Integrity
    content_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash of document content")
    is_accessible = models.BooleanField(default=True, help_text="Whether document URL is still accessible")
    last_accessibility_check = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['opportunity', 'document_type']),
            models.Index(fields=['extraction_status']),
            models.Index(fields=['agent_analysis_status']),
            models.Index(fields=['content_extracted']),
            models.Index(fields=['is_accessible']),
        ]
        unique_together = ['opportunity', 'url']  # Prevent duplicate URLs per opportunity
    
    def __str__(self):
        return f"{self.opportunity.solicitation_number} - {self.name}"
    
    @property
    def is_processable(self):
        """Check if document can be processed for text extraction."""
        processable_types = ['.pdf', '.docx', '.doc', '.txt', '.rtf', '.html', '.htm']
        return any(self.file_extension.lower().endswith(ext) for ext in processable_types)
    
    @property
    def extraction_progress(self):
        """Get extraction progress as percentage."""
        if self.extraction_status == 'completed':
            return 100
        elif self.extraction_status == 'processing':
            return 50
        elif self.extraction_status == 'failed':
            return 0
        else:
            return 0
    
    def record_view(self, user=None):
        """Record that this document was viewed."""
        from django.utils import timezone
        now = timezone.now()
        
        if not self.first_viewed_at:
            self.first_viewed_at = now
        self.last_viewed_at = now
        self.view_count += 1
        self.save(update_fields=['first_viewed_at', 'last_viewed_at', 'view_count'])
    
    def record_download(self, user=None):
        """Record that this document was downloaded."""
        self.download_count += 1
        self.save(update_fields=['download_count'])


class DocumentExtractionSession(BaseModel):
    """
    Track document extraction sessions for LangExtract integration.
    Provides audit trail and batch processing capabilities.
    """
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='extraction_sessions')
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Session Configuration
    extraction_type = models.CharField(max_length=50, choices=[
        ('full_opportunity', 'Full Opportunity Analysis'),
        ('document_only', 'Individual Document'),
        ('compliance_check', 'Compliance Requirements'),
        ('requirement_extraction', 'Requirement Extraction'),
    ], default='full_opportunity')
    
    # Processing Status
    session_status = models.CharField(max_length=50, choices=[
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='queued')
    
    # Documents in Session
    documents = models.ManyToManyField(OpportunityDocument, blank=True, related_name='extraction_sessions')
    total_documents = models.IntegerField(default=0)
    processed_documents = models.IntegerField(default=0)
    failed_documents = models.IntegerField(default=0)
    
    # Results
    extraction_results = models.JSONField(default=dict, blank=True, help_text="Combined extraction results")
    langextract_confidence_scores = models.JSONField(default=dict, blank=True, help_text="Confidence metrics")
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Error Handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['opportunity', 'session_status']),
            models.Index(fields=['extraction_type']),
            models.Index(fields=['session_status']),
        ]
    
    def __str__(self):
        return f"{self.opportunity.solicitation_number} - {self.extraction_type} ({self.session_status})"
    
    @property
    def progress_percentage(self):
        """Calculate processing progress as percentage."""
        if self.total_documents == 0:
            return 0
        return (self.processed_documents / self.total_documents) * 100
    
    @property
    def is_running(self):
        """Check if extraction session is currently running."""
        return self.session_status in ['queued', 'processing']