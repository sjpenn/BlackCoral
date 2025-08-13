from django.db import models
from apps.core.models import BaseModel


class ComplianceRule(BaseModel):
    """
    FAR and agency-specific compliance rules.
    """
    name = models.CharField(max_length=255)
    description = models.TextField()
    rule_type = models.CharField(
        max_length=20,
        choices=[
            ('far', 'Federal Acquisition Regulation'),
            ('agency', 'Agency-Specific'),
            ('security', 'Security Requirement'),
            ('certification', 'Certification Requirement'),
        ]
    )
    agency = models.ForeignKey('core.Agency', on_delete=models.CASCADE, null=True, blank=True)
    rule_text = models.TextField()
    keywords = models.JSONField(default=list)
    severity = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium'
    )
    
    def __str__(self):
        return self.name


class ComplianceCheck(BaseModel):
    """
    Compliance check results for opportunities and documents.
    """
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE, null=True, blank=True)
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, null=True, blank=True)
    rule = models.ForeignKey(ComplianceRule, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ('compliant', 'Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('warning', 'Warning'),
            ('needs_review', 'Needs Review'),
        ]
    )
    details = models.TextField()
    auto_detected = models.BooleanField(default=True)
    reviewed_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.rule.name} - {self.status}"