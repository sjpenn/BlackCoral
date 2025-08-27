"""
Enhanced admin interface for BLACK CORAL Document AI system.
Includes comprehensive document processing, analysis, and chat features.
"""

from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json
from django.contrib import admin
from .models import (
    Document, DocumentTemplate, AssemblyConfiguration, DocumentSection,
    DocumentVariable, ExportFormat, ExportJob, DocumentUpload,
    DocumentChunk, ChatSession, ChatMessage, DocumentAnalysisResult,
    DocumentProcessingPipeline, DocumentSecurity, DocumentShare
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'opportunity', 'file_type', 'processing_status', 'has_ai_analysis', 'has_embeddings', 'created_at']
    list_filter = ['processing_status', 'file_type', 'document_type', 'is_sow', 'is_pws', 'has_embeddings']
    search_fields = ['title', 'opportunity__title', 'opportunity__solicitation_number']
    readonly_fields = ['is_processed', 'has_text', 'has_ai_analysis', 'embedding_status', 'created_at', 'updated_at', 'processed_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('opportunity', 'title', 'file_path', 'file_type', 'file_size')
        }),
        ('Document Metadata', {
            'fields': ('source_url', 'document_type')
        }),
        ('Processing', {
            'fields': ('processing_status', 'processing_error', 'processed_at', 'is_processed', 'has_text')
        }),
        ('AI Analysis', {
            'fields': ('has_ai_analysis', 'is_sow', 'is_pws', 'contains_requirements', 'contains_technical_specs', 
                      'contains_terms_conditions', 'contains_pricing_info', 'summary', 'key_requirements', 'compliance_notes', 
                      'ai_analysis_results')
        }),
        ('Vector Embeddings', {
            'fields': ('has_embeddings', 'embedding_status', 'embedding_updated_at')
        }),
        ('OCR and Layout', {
            'fields': ('ocr_confidence', 'layout_analysis')
        }),
        ('Extracted Content', {
            'fields': ('extracted_text',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['reprocess_documents', 'generate_embeddings', 'run_ai_analysis']
    
    def reprocess_documents(self, request, queryset):
        from .tasks import parse_document
        count = 0
        for doc in queryset:
            parse_document.delay(doc.id)
            count += 1
        self.message_user(request, f"Queued {count} documents for reprocessing.")
    reprocess_documents.short_description = "Reprocess selected documents"
    
    def generate_embeddings(self, request, queryset):
        from .tasks import generate_document_embeddings
        count = 0
        for doc in queryset.filter(processing_status='completed'):
            generate_document_embeddings.delay(doc.id)
            count += 1
        self.message_user(request, f"Queued {count} documents for embedding generation.")
    generate_embeddings.short_description = "Generate embeddings for selected documents"
    
    def run_ai_analysis(self, request, queryset):
        from .tasks import analyze_document_with_ai
        count = 0
        for doc in queryset.filter(processing_status='completed'):
            analyze_document_with_ai.delay(doc.id, 'comprehensive')
            count += 1
        self.message_user(request, f"Queued {count} documents for AI analysis.")
    run_ai_analysis.short_description = "Run AI analysis on selected documents"


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'team', 'is_default', 'is_active', 'created_by', 'created_at']
    list_filter = ['template_type', 'is_default', 'is_active']
    search_fields = ['name', 'description', 'team__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'template_type')
        }),
        ('Template Content', {
            'fields': ('content_template', 'variables')
        }),
        ('Access and Organization', {
            'fields': ('team', 'is_default', 'is_active', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


class DocumentSectionInline(admin.TabularInline):
    model = DocumentSection
    extra = 0
    readonly_fields = ['created_at']
    fields = ['proposal_section', 'order', 'include_in_toc', 'page_break_before', 'page_break_after', 'custom_title', 'custom_numbering']


class DocumentVariableInline(admin.TabularInline):
    model = DocumentVariable
    extra = 0
    readonly_fields = ['created_at']
    fields = ['name', 'display_name', 'variable_type', 'default_value', 'current_value', 'is_required']


@admin.register(AssemblyConfiguration)
class AssemblyConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'team', 'base_template', 'is_default', 'created_by', 'created_at']
    list_filter = ['is_default', 'page_size', 'font_family']
    search_fields = ['name', 'description', 'team__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DocumentSectionInline, DocumentVariableInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('team', 'name', 'description', 'base_template')
        }),
        ('Generation Settings', {
            'fields': ('include_cover_page', 'include_table_of_contents', 'include_executive_summary', 'include_appendices')
        }),
        ('Formatting Options', {
            'fields': (
                'page_size', 'font_family', 'font_size', 'line_spacing',
                ('margin_top', 'margin_bottom'), ('margin_left', 'margin_right')
            )
        }),
        ('Metadata', {
            'fields': ('is_default', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DocumentSection)
class DocumentSectionAdmin(admin.ModelAdmin):
    list_display = ['assembly_config', 'proposal_section', 'order', 'include_in_toc', 'custom_title']
    list_filter = ['include_in_toc', 'page_break_before', 'page_break_after']
    search_fields = ['assembly_config__name', 'proposal_section__title', 'custom_title']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Section Mapping', {
            'fields': ('assembly_config', 'proposal_section', 'order')
        }),
        ('Display Options', {
            'fields': ('include_in_toc', 'page_break_before', 'page_break_after')
        }),
        ('Custom Formatting', {
            'fields': ('custom_title', 'custom_numbering')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DocumentVariable)
class DocumentVariableAdmin(admin.ModelAdmin):
    list_display = ['assembly_config', 'name', 'display_name', 'variable_type', 'is_required']
    list_filter = ['variable_type', 'is_required']
    search_fields = ['assembly_config__name', 'name', 'display_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Variable Definition', {
            'fields': ('assembly_config', 'name', 'display_name', 'description', 'variable_type')
        }),
        ('Value Settings', {
            'fields': ('default_value', 'current_value', 'is_required')
        }),
        ('Calculated Variables', {
            'fields': ('calculation_formula',),
            'description': 'For calculated variable types only'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ExportFormat)
class ExportFormatAdmin(admin.ModelAdmin):
    list_display = ['name', 'format_type', 'is_active', 'requires_external_service']
    list_filter = ['format_type', 'is_active', 'requires_external_service']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'format_type', 'description', 'is_active')
        }),
        ('Format Settings', {
            'fields': ('settings',)
        }),
        ('External Service', {
            'fields': ('requires_external_service', 'external_service_config')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'assembly_config', 'export_format', 'status', 'progress_percentage', 'requested_by', 'created_at']
    list_filter = ['status', 'export_format__format_type', 'created_at']
    search_fields = ['job_id', 'assembly_config__name', 'requested_by__username']
    readonly_fields = ['job_id', 'created_at', 'updated_at', 'started_at', 'completed_at', 'duration']
    
    fieldsets = (
        ('Job Details', {
            'fields': ('job_id', 'assembly_config', 'export_format', 'requested_by')
        }),
        ('Status and Progress', {
            'fields': ('status', 'progress_percentage')
        }),
        ('Results', {
            'fields': ('output_file', 'file_size')
        }),
        ('Processing Details', {
            'fields': ('started_at', 'completed_at', 'duration', 'error_message')
        }),
        ('Parameters', {
            'fields': ('parameters',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def duration(self, obj):
        return obj.duration
    duration.short_description = 'Duration'


@admin.register(DocumentUpload)
class DocumentUploadAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'user', 'status', 'file_size_mb', 'is_safe', 'created_at']
    list_filter = ['status', 'is_safe', 'mime_type', 'created_at']
    search_fields = ['original_filename', 'user__username', 'file_hash']
    readonly_fields = ['file_hash', 'file_size_mb', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Upload Information', {
            'fields': ('user', 'opportunity', 'original_filename', 'file_size', 'file_size_mb', 'mime_type')
        }),
        ('Processing Status', {
            'fields': ('status', 'upload_progress', 'error_message')
        }),
        ('Security Validation', {
            'fields': ('is_safe', 'virus_scan_result', 'security_flags', 'validation_errors')
        }),
        ('Results', {
            'fields': ('created_document', 'metadata_extracted')
        }),
        ('Audit Trail', {
            'fields': ('ip_address', 'user_agent', 'file_hash')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def file_size_mb(self, obj):
        return obj.file_size_mb
    file_size_mb.short_description = 'Size (MB)'


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'preview_text', 'page_number', 'section_title']
    list_filter = ['document__file_type', 'semantic_role']
    search_fields = ['document__title', 'text', 'section_title']
    readonly_fields = ['preview_text', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Chunk Information', {
            'fields': ('document', 'chunk_index', 'text', 'preview_text')
        }),
        ('Context', {
            'fields': ('page_number', 'section_title', 'semantic_role', 'metadata')
        }),
        ('Embeddings', {
            'fields': ('embedding_vector', 'embedding_model')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'message_count', 'document_count', 'is_active', 'updated_at']
    list_filter = ['is_active', 'ai_provider', 'use_rag', 'created_at']
    search_fields = ['title', 'user__username', 'opportunity__title']
    readonly_fields = ['message_count', 'document_count', 'created_at', 'updated_at']
    filter_horizontal = ['documents']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'opportunity', 'title', 'system_prompt')
        }),
        ('Documents', {
            'fields': ('documents',)
        }),
        ('AI Configuration', {
            'fields': ('ai_provider', 'temperature', 'max_tokens')
        }),
        ('RAG Settings', {
            'fields': ('use_rag', 'max_context_chunks', 'similarity_threshold')
        }),
        ('Status', {
            'fields': ('is_active', 'message_count', 'document_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'message_type', 'content_preview', 'has_citations', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['session__title', 'content']
    readonly_fields = ['has_citations', 'context_count', 'created_at']
    
    fieldsets = (
        ('Message Information', {
            'fields': ('session', 'message_type', 'content')
        }),
        ('Context and Citations', {
            'fields': ('context_chunks', 'citations', 'has_citations', 'context_count')
        }),
        ('AI Metadata', {
            'fields': ('tokens_used', 'response_time', 'confidence_score')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(DocumentAnalysisResult)
class DocumentAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['document', 'analysis_type_display', 'confidence_score', 'quality_score', 'ai_provider', 'created_at']
    list_filter = ['analysis_type', 'ai_provider', 'created_at']
    search_fields = ['document__title', 'ai_provider', 'model_version']
    readonly_fields = ['quality_score', 'processing_time', 'created_at']
    
    def analysis_type_display(self, obj):
        """Display analysis type in a human-readable format"""
        return obj.get_analysis_type_display() if hasattr(obj, 'get_analysis_type_display') else obj.analysis_type
    analysis_type_display.short_description = 'Analysis Type'
    
    fieldsets = (
        ('Analysis Information', {
            'fields': ('document', 'analysis_type', 'ai_provider', 'model_version')
        }),
        ('Results', {
            'fields': ('results', 'confidence_score', 'quality_score')
        }),
        ('Quality Metrics', {
            'fields': ('accuracy_score', 'completeness_score', 'processing_time')
        }),
        ('Configuration', {
            'fields': ('analysis_parameters',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )


@admin.register(DocumentProcessingPipeline)
class DocumentProcessingPipelineAdmin(admin.ModelAdmin):
    list_display = ['document', 'pipeline_name', 'status', 'progress_percentage', 'is_running', 'created_at']
    list_filter = ['status', 'pipeline_name', 'created_at']
    search_fields = ['document__title', 'pipeline_name']
    readonly_fields = ['is_running', 'duration', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Pipeline Information', {
            'fields': ('document', 'pipeline_name', 'status')
        }),
        ('Progress', {
            'fields': ('current_stage', 'stages_completed', 'total_stages', 'progress_percentage', 'is_running')
        }),
        ('Configuration', {
            'fields': ('stages',)
        }),
        ('Results', {
            'fields': ('stage_results', 'performance_metrics', 'error_log')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DocumentSecurity)
class DocumentSecurityAdmin(admin.ModelAdmin):
    list_display = ['document', 'classification_display', 'clearance_required', 'classification_authority', 'classification_date']
    list_filter = ['classification', 'clearance_required', 'classification_date']
    search_fields = ['document__title', 'classification_authority__username']
    readonly_fields = ['classification_date', 'created_at', 'updated_at']
    filter_horizontal = ['authorized_users']
    
    def classification_display(self, obj):
        """Display classification in a human-readable format"""
        return obj.get_classification_display() if hasattr(obj, 'get_classification_display') else obj.classification
    classification_display.short_description = 'Classification'
    
    fieldsets = (
        ('Document Security', {
            'fields': ('document', 'classification', 'classification_authority')
        }),
        ('Access Control', {
            'fields': ('authorized_users', 'authorized_roles', 'clearance_required')
        }),
        ('Handling Instructions', {
            'fields': ('handling_instructions', 'dissemination_controls')
        }),
        ('Audit Log', {
            'fields': ('access_log',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('classification_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ['document', 'shared_by', 'shared_with_display', 'share_type', 'status', 'access_count', 'created_at']
    list_filter = ['share_type', 'status', 'password_protected', 'created_at']
    search_fields = ['document__title', 'shared_by__username', 'shared_with__username', 'shared_with_email']
    readonly_fields = ['access_token', 'access_count', 'last_accessed', 'is_expired', 'is_active', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Share Information', {
            'fields': ('document', 'shared_by', 'shared_with', 'shared_with_email')
        }),
        ('Share Configuration', {
            'fields': ('share_type', 'status', 'expires_at', 'password_protected')
        }),
        ('Access Control', {
            'fields': ('access_token', 'access_count', 'last_accessed', 'is_expired', 'is_active')
        }),
        ('Notifications', {
            'fields': ('notify_on_access', 'access_notifications')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def shared_with_display(self, obj):
        if obj.shared_with:
            return obj.shared_with.username
        return obj.shared_with_email or 'External User'
    shared_with_display.short_description = 'Shared With'