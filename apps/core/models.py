from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Base model for all BLACK CORAL models with common fields.
    """
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class NAICSCode(BaseModel):
    """
    NAICS (North American Industry Classification System) codes for filtering opportunities.
    """
    code = models.CharField(max_length=10, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    parent_code = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    level = models.IntegerField(default=1)  # 2-digit, 3-digit, 4-digit, 5-digit, 6-digit

    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['level']),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"


class Agency(BaseModel):
    """
    Government agencies that post opportunities.
    """
    name = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    contact_info = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Agencies"
        ordering = ['name']

    def __str__(self):
        return f"{self.abbreviation} - {self.name}"


class CapabilitySet(BaseModel):
    """
    Internal capability sets for matching opportunities.
    """
    name = models.CharField(max_length=255)
    description = models.TextField()
    naics_codes = models.ManyToManyField(NAICSCode, blank=True)
    keywords = models.JSONField(default=list, help_text="List of keywords associated with this capability")

    def __str__(self):
        return self.name