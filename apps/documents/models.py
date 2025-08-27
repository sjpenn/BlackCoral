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
    Documents associated with opportunities (SOW, PWS, attachments) with advanced AI processing.
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
    
    # Enhanced PDF Content (new fields for PyMuPDF extraction)
    extracted_markdown = models.TextField(blank=True, help_text="PDF content in markdown format")
    pdf_pages_data = models.JSONField(default=list, blank=True, help_text="Per-page PDF content and metadata")
    pdf_extraction_method = models.CharField(max_length=20, blank=True, choices=[
        ('pymupdf4llm', 'PyMuPDF4LLM'),
        ('pymupdf', 'PyMuPDF'),
        ('fallback', 'Fallback Method'),
    ])
    pdf_metadata = models.JSONField(default=dict, blank=True, help_text="PDF document metadata from PyMuPDF")
    
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
    
    # Enhanced Analysis flags
    is_sow = models.BooleanField(default=False, help_text="Is this a Statement of Work?")
    is_pws = models.BooleanField(default=False, help_text="Is this a Performance Work Statement?")
    contains_requirements = models.BooleanField(default=False)
    contains_technical_specs = models.BooleanField(default=False)
    contains_terms_conditions = models.BooleanField(default=False)
    contains_pricing_info = models.BooleanField(default=False)
    
    # AI Analysis Results
    summary = models.TextField(blank=True)
    key_requirements = models.JSONField(default=list, blank=True)
    compliance_notes = models.JSONField(default=list, blank=True)
    ai_analysis_results = models.JSONField(default=dict, blank=True, help_text="Comprehensive AI analysis results")
    
    # Vector embeddings for RAG
    has_embeddings = models.BooleanField(default=False)
    embedding_updated_at = models.DateTimeField(null=True, blank=True)
    
    # OCR and Layout Analysis
    ocr_confidence = models.FloatField(null=True, blank=True, help_text="OCR confidence score 0-1")
    layout_analysis = models.JSONField(default=dict, blank=True, help_text="Layout structure analysis")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['opportunity', 'processing_status']),
            models.Index(fields=['document_type']),
            models.Index(fields=['has_embeddings']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.file_type})"
    
    @property
    def is_processed(self):
        return self.processing_status == 'completed'
    
    @property
    def has_text(self):
        return bool(self.extracted_text and len(self.extracted_text) > 0)
    
    @property
    def has_ai_analysis(self):
        return bool(self.ai_analysis_results)
    
    @property
    def embedding_status(self):
        if not self.has_embeddings:
            return 'not_generated'
        if self.embedding_updated_at and self.updated_at > self.embedding_updated_at:
            return 'outdated'
        return 'current'
    
    @property
    def has_pdf_content(self):
        """Check if PDF content has been extracted"""
        return bool(self.extracted_markdown or self.pdf_pages_data)
    
    @property
    def total_pages(self):
        """Get total number of pages from PDF extraction"""
        if self.pdf_pages_data:
            return len(self.pdf_pages_data)
        elif self.pdf_metadata.get('page_count'):
            return self.pdf_metadata['page_count']
        return 0
    
    @property
    def is_pdf(self):
        """Check if this is a PDF document"""
        return self.file_type.lower() == 'pdf'
    
    def get_page_content(self, page_number: int = 1):
        """Get content for a specific page"""
        if not self.pdf_pages_data or page_number < 1:
            return None
        
        try:
            # Page numbers are 1-based in UI, but 0-based in list
            page_index = page_number - 1
            if page_index < len(self.pdf_pages_data):
                return self.pdf_pages_data[page_index]
        except (IndexError, TypeError):
            pass
        
        return None


class DocumentChunk(BaseModel):
    """
    Text chunks from documents for semantic search and RAG.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField(help_text="Order of chunk in document")
    text = models.TextField(help_text="Chunk text content")
    metadata = models.JSONField(default=dict, blank=True, help_text="Chunk metadata (page, section, etc.)")
    
    # Embeddings
    embedding_vector = models.JSONField(null=True, blank=True, help_text="Vector embedding of chunk")
    embedding_model = models.CharField(max_length=100, blank=True, help_text="Model used for embedding")
    
    # Context information
    page_number = models.PositiveIntegerField(null=True, blank=True)
    section_title = models.CharField(max_length=255, blank=True)
    semantic_role = models.CharField(max_length=100, blank=True, help_text="requirement, specification, etc.")
    
    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = [['document', 'chunk_index']]
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['semantic_role']),
        ]
    
    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_index}"
    
    @property
    def preview_text(self):
        return self.text[:200] + "..." if len(self.text) > 200 else self.text


class DocumentExtractionSession(BaseModel):
    """
    Track document extraction and processing sessions.
    """
    EXTRACTION_TYPE_CHOICES = [
        ('full_text', 'Full Text Extraction'),
        ('structured', 'Structured Data Extraction'),
        ('semantic', 'Semantic Analysis'),
        ('compliance', 'Compliance Check'),
        ('requirements', 'Requirements Extraction'),
        ('pricing', 'Pricing Information'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='extraction_sessions')
    extraction_type = models.CharField(max_length=20, choices=EXTRACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Processing details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.DurationField(null=True, blank=True)
    
    # Results
    extracted_data = models.JSONField(default=dict, blank=True)
    confidence_scores = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    
    # Configuration
    extraction_parameters = models.JSONField(default=dict, blank=True)
    ai_provider = models.CharField(max_length=50, blank=True, help_text="AI provider used")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'extraction_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.document.title} - {self.get_extraction_type_display()}"
    
    @property
    def is_complete(self):
        return self.status == 'completed'
    
    @property
    def success_rate(self):
        if not self.confidence_scores:
            return None
        scores = list(self.confidence_scores.values())
        return sum(scores) / len(scores) if scores else 0


class ChatSession(BaseModel):
    """
    AI chat sessions for document-based conversations.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_chat_sessions')
    documents = models.ManyToManyField(Document, related_name='chat_sessions', blank=True)
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE, null=True, blank=True)
    
    title = models.CharField(max_length=255, help_text="Chat session title")
    system_prompt = models.TextField(blank=True, help_text="System prompt for the AI")
    
    # Session configuration
    ai_provider = models.CharField(max_length=50, default='claude', help_text="AI provider for chat")
    temperature = models.FloatField(default=0.7, help_text="AI temperature setting")
    max_tokens = models.PositiveIntegerField(default=4000, help_text="Max tokens per response")
    
    # Context settings
    use_rag = models.BooleanField(default=True, help_text="Use RAG for context")
    max_context_chunks = models.PositiveIntegerField(default=10, help_text="Max chunks for context")
    similarity_threshold = models.FloatField(default=0.7, help_text="Similarity threshold for chunk retrieval")
    
    # Session state
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['opportunity']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    @property
    def message_count(self):
        return self.messages.count()
    
    @property
    def document_count(self):
        return self.documents.count()


class ChatMessage(BaseModel):
    """
    Messages in document chat sessions.
    """
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User Message'),
        ('assistant', 'Assistant Message'),
        ('system', 'System Message'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField(help_text="Message content")
    
    # Context and citations
    context_chunks = models.JSONField(default=list, blank=True, help_text="Document chunks used for context")
    citations = models.JSONField(default=list, blank=True, help_text="Source citations")
    
    # AI metadata
    tokens_used = models.PositiveIntegerField(null=True, blank=True)
    response_time = models.DurationField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['message_type']),
        ]
    
    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.get_message_type_display()}: {preview}"
    
    @property
    def has_citations(self):
        return bool(self.citations)
    
    @property
    def context_count(self):
        return len(self.context_chunks)


class DocumentAnalysisResult(BaseModel):
    """
    Results from specialized document analysis tools.
    """
    ANALYSIS_TYPE_CHOICES = [
        ('requirements_extraction', 'Requirements Extraction'),
        ('compliance_check', 'Compliance Check'),
        ('technical_specifications', 'Technical Specifications'),
        ('pricing_analysis', 'Pricing Analysis'),
        ('risk_assessment', 'Risk Assessment'),
        ('competitor_intelligence', 'Competitor Intelligence'),
        ('proposal_outline', 'Proposal Outline'),
        ('section_mapping', 'Section Mapping'),
        ('keyword_analysis', 'Keyword Analysis'),
        ('sentiment_analysis', 'Sentiment Analysis'),
        ('readability_analysis', 'Readability Analysis'),
        ('structural_analysis', 'Document Structure Analysis'),
        ('entity_extraction', 'Named Entity Extraction'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='analysis_results')
    analysis_type = models.CharField(max_length=30, choices=ANALYSIS_TYPE_CHOICES)
    
    # Analysis results
    results = models.JSONField(default=dict, help_text="Structured analysis results")
    confidence_score = models.FloatField(help_text="Overall confidence in analysis")
    processing_time = models.DurationField(null=True, blank=True)
    
    # Metadata
    ai_provider = models.CharField(max_length=50, help_text="AI provider used")
    model_version = models.CharField(max_length=100, blank=True, help_text="Model version")
    analysis_parameters = models.JSONField(default=dict, blank=True)
    
    # Quality metrics
    accuracy_score = models.FloatField(null=True, blank=True, help_text="Accuracy assessment")
    completeness_score = models.FloatField(null=True, blank=True, help_text="Completeness assessment")
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['document', 'analysis_type']]
        indexes = [
            models.Index(fields=['document', 'analysis_type']),
            models.Index(fields=['analysis_type', 'confidence_score']),
        ]
    
    def __str__(self):
        return f"{self.document.title} - {self.get_analysis_type_display()}"
    
    @property
    def quality_score(self):
        scores = [s for s in [self.confidence_score, self.accuracy_score, self.completeness_score] if s is not None]
        return sum(scores) / len(scores) if scores else self.confidence_score


class DocumentUpload(BaseModel):
    """
    Track document uploads with security validation and virus scanning.
    """
    UPLOAD_STATUS_CHOICES = [
        ('pending', 'Pending Upload'),
        ('uploading', 'Uploading'),
        ('validating', 'Validating'),
        ('scanning', 'Virus Scanning'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_uploads')
    opportunity = models.ForeignKey('opportunities.Opportunity', on_delete=models.CASCADE, null=True, blank=True)
    
    # Upload details
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=64, help_text="SHA-256 hash of file")
    
    # Processing status
    status = models.CharField(max_length=20, choices=UPLOAD_STATUS_CHOICES, default='pending')
    upload_progress = models.PositiveIntegerField(default=0, help_text="Upload progress percentage")
    
    # Security validation
    virus_scan_result = models.JSONField(default=dict, blank=True)
    security_flags = models.JSONField(default=list, blank=True)
    is_safe = models.BooleanField(null=True, blank=True)
    
    # File validation
    validation_errors = models.JSONField(default=list, blank=True)
    metadata_extracted = models.JSONField(default=dict, blank=True)
    
    # Processing results
    created_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['file_hash']),
            models.Index(fields=['opportunity', 'status']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} - {self.get_status_display()}"
    
    @property
    def is_complete(self):
        return self.status == 'completed'
    
    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)


class DocumentProcessingPipeline(BaseModel):
    """
    Track document processing pipeline with stages and dependencies.
    """
    PIPELINE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='processing_pipelines')
    pipeline_name = models.CharField(max_length=100, help_text="Name of processing pipeline")
    status = models.CharField(max_length=20, choices=PIPELINE_STATUS_CHOICES, default='pending')
    
    # Pipeline configuration
    stages = models.JSONField(default=list, help_text="List of processing stages")
    current_stage = models.PositiveIntegerField(default=0)
    
    # Progress tracking
    stages_completed = models.PositiveIntegerField(default=0)
    total_stages = models.PositiveIntegerField(default=0)
    progress_percentage = models.PositiveIntegerField(default=0)
    
    # Results and metrics
    stage_results = models.JSONField(default=dict, blank=True)
    performance_metrics = models.JSONField(default=dict, blank=True)
    error_log = models.JSONField(default=list, blank=True)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'status']),
            models.Index(fields=['pipeline_name', 'status']),
        ]
    
    def __str__(self):
        return f"{self.document.title} - {self.pipeline_name}"
    
    @property
    def is_running(self):
        return self.status in ['pending', 'running']
    
    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class DocumentSecurity(BaseModel):
    """
    Security classification and access control for documents.
    """
    CLASSIFICATION_CHOICES = [
        ('unclassified', 'Unclassified'),
        ('cui', 'Controlled Unclassified Information'),
        ('confidential', 'Confidential'),
        ('secret', 'Secret'),
        ('top_secret', 'Top Secret'),
    ]
    
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='security')
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default='unclassified')
    
    # Access control
    authorized_users = models.ManyToManyField(User, blank=True, related_name='authorized_documents')
    authorized_roles = models.JSONField(default=list, blank=True)
    clearance_required = models.CharField(max_length=50, blank=True)
    
    # Handling instructions
    handling_instructions = models.TextField(blank=True)
    dissemination_controls = models.JSONField(default=list, blank=True)
    
    # Audit
    access_log = models.JSONField(default=list, blank=True)
    classification_authority = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='classified_documents')
    classification_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['classification']),
            models.Index(fields=['clearance_required']),
        ]
    
    def __str__(self):
        return f"{self.document.title} - {self.get_classification_display()}"
    
    def can_user_access(self, user):
        """Check if user can access this document."""
        # Admins can access everything
        if user.role == User.Role.ADMIN:
            return True
        
        # Check explicit authorization
        if self.authorized_users.filter(id=user.id).exists():
            return True
        
        # Check role-based access
        if user.role.value in self.authorized_roles:
            return True
        
        # Check clearance level
        if self.clearance_required and hasattr(user, 'security_clearance'):
            return user.security_clearance == self.clearance_required
        
        # Default deny for classified documents
        if self.classification != 'unclassified':
            return False
        
        return True
    
    def log_access(self, user, action='view'):
        """Log document access."""
        from django.utils import timezone
        access_entry = {
            'user_id': user.id,
            'username': user.username,
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'ip_address': getattr(user, '_current_ip', None),
        }
        
        if not isinstance(self.access_log, list):
            self.access_log = []
        
        self.access_log.append(access_entry)
        
        # Keep only last 1000 entries
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]
        
        self.save(update_fields=['access_log'])


class DocumentShare(BaseModel):
    """
    Document sharing and collaboration.
    """
    SHARE_TYPE_CHOICES = [
        ('view', 'View Only'),
        ('comment', 'Comment'),
        ('edit', 'Edit'),
        ('admin', 'Admin'),
    ]
    
    SHARE_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='shares')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_documents')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_document_shares', null=True, blank=True)
    shared_with_email = models.EmailField(blank=True, help_text="Email for external sharing")
    
    # Share configuration
    share_type = models.CharField(max_length=20, choices=SHARE_TYPE_CHOICES, default='view')
    status = models.CharField(max_length=20, choices=SHARE_STATUS_CHOICES, default='active')
    
    # Access control
    expires_at = models.DateTimeField(null=True, blank=True)
    password_protected = models.BooleanField(default=False)
    access_token = models.CharField(max_length=64, unique=True, help_text="Secure access token")
    
    # Usage tracking
    access_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    # Notification settings
    notify_on_access = models.BooleanField(default=False)
    access_notifications = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'status']),
            models.Index(fields=['shared_with', 'status']),
            models.Index(fields=['access_token']),
        ]
        unique_together = [['document', 'shared_with'], ['document', 'shared_with_email']]
    
    def __str__(self):
        target = self.shared_with.username if self.shared_with else self.shared_with_email
        return f"{self.document.title} -> {target}"
    
    def save(self, *args, **kwargs):
        if not self.access_token:
            import secrets
            self.access_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_active(self):
        return self.status == 'active' and not self.is_expired
    
    def record_access(self):
        """Record document access."""
        from django.utils import timezone
        self.access_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['access_count', 'last_accessed'])


class DocumentChatMessage(BaseModel):
    """Chat messages for document-based conversations"""
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User Message'),
        ('assistant', 'AI Assistant Message'),
        ('system', 'System Message'),
    ]
    
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='chat_messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_chat_messages')
    session_id = models.CharField(max_length=255, db_index=True, help_text="Chat session identifier")
    
    # Message content
    message = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='user')
    
    # AI-specific fields
    context_used = models.JSONField(default=list, blank=True, help_text="Context snippets used for AI response")
    confidence_score = models.FloatField(null=True, blank=True, help_text="AI confidence score (0.0-1.0)")
    ai_provider = models.CharField(max_length=50, blank=True, help_text="AI provider used")
    processing_time = models.FloatField(null=True, blank=True, help_text="Processing time in seconds")
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['document', 'session_id', 'created_at']),
            models.Index(fields=['user', 'document']),
            models.Index(fields=['session_id', 'message_type']),
        ]
    
    def __str__(self):
        return f"{self.message_type} message in {self.document.title} session {self.session_id}"