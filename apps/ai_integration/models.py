from django.db import models
from apps.core.models import BaseModel


class AITask(BaseModel):
    """
    Track AI processing tasks and results.
    """
    TASK_TYPES = [
        ('summarize', 'Summarize Document'),
        ('analyze', 'Analyze Requirements'),
        ('draft', 'Draft Content'),
        ('compliance', 'Compliance Check'),
        ('quality', 'Quality Review'),
    ]
    
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE, null=True, blank=True)
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, null=True, blank=True)
    input_data = models.JSONField()
    output_data = models.JSONField(null=True, blank=True)
    ai_service = models.CharField(max_length=50)  # claude, gemini, etc.
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
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_task_type_display()} - {self.status}"