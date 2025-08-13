from django.db import models
from apps.core.models import BaseModel


class Document(BaseModel):
    """
    Documents associated with opportunities (SOW, PWS, attachments).
    """
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='documents/%Y/%m/')
    file_type = models.CharField(max_length=10)  # PDF, DOCX, etc.
    file_size = models.PositiveIntegerField()
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
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.file_type})"