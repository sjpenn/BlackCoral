from django.db import models
from apps.core.models import BaseModel


class Opportunity(BaseModel):
    """
    Government contracting opportunity from sam.gov and other sources.
    """
    title = models.CharField(max_length=500)
    solicitation_number = models.CharField(max_length=100, unique=True)
    agency = models.ForeignKey('core.Agency', on_delete=models.CASCADE)
    naics_codes = models.ManyToManyField('core.NAICSCode', blank=True)
    description = models.TextField()
    posted_date = models.DateTimeField()
    response_date = models.DateTimeField(null=True, blank=True)
    award_date = models.DateTimeField(null=True, blank=True)
    source_url = models.URLField()
    source_api = models.CharField(max_length=50, default='sam.gov')
    
    class Meta:
        ordering = ['-posted_date']
        indexes = [
            models.Index(fields=['solicitation_number']),
            models.Index(fields=['posted_date']),
            models.Index(fields=['response_date']),
        ]
    
    def __str__(self):
        return f"{self.solicitation_number} - {self.title[:50]}"