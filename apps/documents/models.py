from django.db import models
from apps.core.models import BaseModel


class Document(BaseModel):
    """
    Documents associated with opportunities (SOW, PWS, attachments).
    """
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='documents/%Y/%m/', null=True, blank=True)
    file_type = models.CharField(max_length=10)  # PDF, DOCX, etc.
    file_size = models.PositiveIntegerField(default=0)
    
    # Document metadata
    source_url = models.URLField(blank=True)
    document_type = models.CharField(max_length=50, blank=True)  # resource, additional_info, etc.
    
    # Processing
    extracted_text = models.TextField(blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    processing_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Analysis flags
    is_sow = models.BooleanField(default=False, help_text="Is this a Statement of Work?")
    is_pws = models.BooleanField(default=False, help_text="Is this a Performance Work Statement?")
    contains_requirements = models.BooleanField(default=False)
    
    # AI Analysis
    summary = models.TextField(blank=True)
    key_requirements = models.JSONField(default=list, blank=True)
    compliance_notes = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['opportunity', 'processing_status']),
            models.Index(fields=['document_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.file_type})"
    
    @property
    def is_processed(self):
        return self.processing_status == 'completed'
    
    @property
    def has_text(self):
        return bool(self.extracted_text and len(self.extracted_text) > 0)