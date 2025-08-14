import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel

User = get_user_model()


class DocumentTemplate(BaseModel):
    """Templates for generating proposal documents"""
    TEMPLATE_TYPE_CHOICES = [
        ('proposal', 'Proposal Template'),
        ('section', 'Section Template'),
        ('cover_page', 'Cover Page Template'),
        ('appendix', 'Appendix Template'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    
    # Template content
    content_template = models.TextField(help_text="HTML template with variables")
    variables = models.JSONField(default=dict, help_text="Available template variables")
    
    # Organization and access
    team = models.ForeignKey('collaboration.ProposalTeam', on_delete=models.CASCADE, related_name='document_templates', null=True, blank=True)
    is_default = models.BooleanField(default=False, help_text="Default template for organization")
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_templates')
    
    class Meta:
        ordering = ['template_type', 'name']
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['team', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class AssemblyConfiguration(BaseModel):
    """Configuration for document assembly and generation"""
    team = models.ForeignKey('collaboration.ProposalTeam', on_delete=models.CASCADE, related_name='assembly_configs')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Template and sections
    base_template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name='assembly_configs')
    sections = models.ManyToManyField('collaboration.ProposalSection', through='DocumentSection')
    
    # Generation settings
    include_cover_page = models.BooleanField(default=True)
    include_table_of_contents = models.BooleanField(default=True)
    include_executive_summary = models.BooleanField(default=True)
    include_appendices = models.BooleanField(default=True)
    
    # Formatting options
    page_size = models.CharField(max_length=10, default='letter', choices=[
        ('letter', 'Letter (8.5" x 11")'),
        ('a4', 'A4'),
        ('legal', 'Legal (8.5" x 14")'),
    ])
    font_family = models.CharField(max_length=50, default='Times New Roman')
    font_size = models.PositiveIntegerField(default=12)
    line_spacing = models.DecimalField(max_digits=3, decimal_places=1, default=1.0)
    margin_top = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    margin_bottom = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    margin_left = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    margin_right = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    
    # Metadata
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['team', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.team.name}"


class DocumentSection(BaseModel):
    """Mapping between proposal sections and document assembly order"""
    assembly_config = models.ForeignKey(AssemblyConfiguration, on_delete=models.CASCADE, related_name='document_sections')
    proposal_section = models.ForeignKey('collaboration.ProposalSection', on_delete=models.CASCADE, related_name='document_mappings')
    
    # Order and display
    order = models.PositiveIntegerField()
    include_in_toc = models.BooleanField(default=True, help_text="Include in table of contents")
    page_break_before = models.BooleanField(default=False, help_text="Insert page break before section")
    page_break_after = models.BooleanField(default=False, help_text="Insert page break after section")
    
    # Custom formatting
    custom_title = models.CharField(max_length=255, blank=True, help_text="Override section title")
    custom_numbering = models.CharField(max_length=50, blank=True, help_text="Custom section numbering")
    
    class Meta:
        ordering = ['assembly_config', 'order']
        unique_together = [['assembly_config', 'proposal_section']]
        indexes = [
            models.Index(fields=['assembly_config', 'order']),
        ]
    
    def __str__(self):
        return f"{self.assembly_config.name} - Section {self.order}"
    
    @property
    def display_title(self):
        return self.custom_title or self.proposal_section.title


class DocumentVariable(BaseModel):
    """Variables available for document templates"""
    VARIABLE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Boolean'),
        ('list', 'List'),
        ('calculated', 'Calculated'),
    ]
    
    assembly_config = models.ForeignKey(AssemblyConfiguration, on_delete=models.CASCADE, related_name='variables')
    name = models.CharField(max_length=100, help_text="Variable name (e.g., 'company_name')")
    display_name = models.CharField(max_length=255, help_text="Human-readable name")
    description = models.TextField(blank=True)
    variable_type = models.CharField(max_length=20, choices=VARIABLE_TYPE_CHOICES)
    
    # Value and defaults
    default_value = models.TextField(blank=True)
    current_value = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)
    
    # For calculated variables
    calculation_formula = models.TextField(blank=True, help_text="Python expression for calculated variables")
    
    class Meta:
        ordering = ['assembly_config', 'name']
        unique_together = [['assembly_config', 'name']]
        indexes = [
            models.Index(fields=['assembly_config', 'variable_type']),
        ]
    
    def __str__(self):
        return f"{self.assembly_config.name} - {self.display_name}"
    
    def get_value(self):
        """Get the current value or default value"""
        return self.current_value or self.default_value


class ExportFormat(BaseModel):
    """Available export formats for documents"""
    FORMAT_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('docx', 'Microsoft Word'),
        ('html', 'HTML'),
        ('txt', 'Plain Text'),
    ]
    
    name = models.CharField(max_length=100)
    format_type = models.CharField(max_length=10, choices=FORMAT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Format-specific settings
    settings = models.JSONField(default=dict, help_text="Format-specific configuration")
    is_active = models.BooleanField(default=True)
    
    # Processing
    requires_external_service = models.BooleanField(default=False)
    external_service_config = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['format_type', 'name']
        indexes = [
            models.Index(fields=['format_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_format_type_display()})"


class ExportJob(BaseModel):
    """Track document export jobs"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Job details
    assembly_config = models.ForeignKey(AssemblyConfiguration, on_delete=models.CASCADE, related_name='export_jobs')
    export_format = models.ForeignKey(ExportFormat, on_delete=models.CASCADE, related_name='export_jobs')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_jobs')
    
    # Status and progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.PositiveIntegerField(default=0)
    
    # Results
    output_file = models.FileField(upload_to='exports/%Y/%m/', null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    
    # Processing details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    job_id = models.UUIDField(default=uuid.uuid4, unique=True, help_text="Unique job identifier")
    parameters = models.JSONField(default=dict, help_text="Export parameters and options")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['assembly_config', 'status']),
            models.Index(fields=['requested_by', 'status']),
            models.Index(fields=['job_id']),
        ]
    
    def __str__(self):
        return f"Export {self.job_id} - {self.assembly_config.name} ({self.export_format.format_type})"
    
    @property
    def is_processing(self):
        return self.status in ['pending', 'processing']
    
    @property
    def is_complete(self):
        return self.status == 'completed'
    
    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


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