"""
BLACK CORAL Documents Admin
Django admin configuration for document assembly models
"""
from django.contrib import admin
from .models import (
    Document, DocumentTemplate, AssemblyConfiguration, DocumentSection,
    DocumentVariable, ExportFormat, ExportJob
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'opportunity', 'file_type', 'processing_status', 'created_at']
    list_filter = ['processing_status', 'file_type', 'document_type', 'is_sow', 'is_pws']
    search_fields = ['title', 'opportunity__title', 'opportunity__solicitation_number']
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('opportunity', 'title', 'file_path', 'file_type', 'file_size')
        }),
        ('Document Metadata', {
            'fields': ('source_url', 'document_type')
        }),
        ('Processing', {
            'fields': ('processing_status', 'processing_error', 'processed_at', 'extracted_text')
        }),
        ('Analysis', {
            'fields': ('is_sow', 'is_pws', 'contains_requirements', 'summary', 'key_requirements', 'compliance_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


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