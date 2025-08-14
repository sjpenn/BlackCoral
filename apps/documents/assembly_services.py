"""
Document Assembly Services
Core business logic for document assembly and generation
"""
import os
import tempfile
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone
from django.core.files.base import ContentFile
from celery import shared_task

from .models import (
    DocumentTemplate, AssemblyConfiguration, DocumentSection,
    DocumentVariable, ExportFormat, ExportJob
)
from apps.collaboration.models import ProposalSection


class DocumentAssemblyEngine:
    """Core engine for assembling documents from sections and templates"""
    
    def __init__(self, assembly_config: AssemblyConfiguration):
        self.assembly_config = assembly_config
        self.variables = {}
        self._load_variables()
    
    def _load_variables(self):
        """Load all variables for this assembly configuration"""
        for var in self.assembly_config.variables.all():
            self.variables[var.name] = var.get_value()
    
    def set_variable(self, name: str, value: str):
        """Set a variable value"""
        self.variables[name] = value
        # Update the database
        try:
            var = self.assembly_config.variables.get(name=name)
            var.current_value = value
            var.save()
        except DocumentVariable.DoesNotExist:
            pass
    
    def get_variable(self, name: str, default: str = "") -> str:
        """Get a variable value"""
        return self.variables.get(name, default)
    
    def assemble_document(self) -> str:
        """Assemble the complete document HTML"""
        sections_html = []
        
        # Get ordered sections
        document_sections = self.assembly_config.document_sections.all().order_by('order')
        
        for doc_section in document_sections:
            section_html = self._render_section(doc_section)
            if section_html:
                sections_html.append(section_html)
        
        # Render the base template with sections
        base_template = Template(self.assembly_config.base_template.content_template)
        context = Context({
            'sections': sections_html,
            'config': self.assembly_config,
            'variables': self.variables,
            'assembly_date': timezone.now(),
            'include_cover_page': self.assembly_config.include_cover_page,
            'include_table_of_contents': self.assembly_config.include_table_of_contents,
            'include_executive_summary': self.assembly_config.include_executive_summary,
            'include_appendices': self.assembly_config.include_appendices,
        })
        
        return base_template.render(context)
    
    def _render_section(self, doc_section: DocumentSection) -> str:
        """Render a single document section"""
        proposal_section = doc_section.proposal_section
        
        # Skip if section has no content
        if not proposal_section.content:
            return ""
        
        section_html = f"""
        <div class="document-section" data-section-id="{proposal_section.id}">
            {self._render_section_header(doc_section)}
            <div class="section-content">
                {proposal_section.content}
            </div>
            {self._render_section_footer(doc_section)}
        </div>
        """
        
        if doc_section.page_break_before:
            section_html = '<div class="page-break"></div>' + section_html
        
        if doc_section.page_break_after:
            section_html = section_html + '<div class="page-break"></div>'
        
        return section_html
    
    def _render_section_header(self, doc_section: DocumentSection) -> str:
        """Render section header with title and numbering"""
        title = doc_section.display_title
        numbering = doc_section.custom_numbering or doc_section.proposal_section.section_number
        
        return f"""
        <div class="section-header">
            <h2 class="section-title">
                <span class="section-number">{numbering}</span>
                <span class="section-title-text">{title}</span>
            </h2>
        </div>
        """
    
    def _render_section_footer(self, doc_section: DocumentSection) -> str:
        """Render section footer if needed"""
        return ""
    
    def get_table_of_contents(self) -> List[Dict[str, Any]]:
        """Generate table of contents data"""
        toc_items = []
        
        document_sections = self.assembly_config.document_sections.filter(
            include_in_toc=True
        ).order_by('order')
        
        for doc_section in document_sections:
            toc_items.append({
                'title': doc_section.display_title,
                'numbering': doc_section.custom_numbering or doc_section.proposal_section.section_number,
                'page': None,  # Will be filled during export
                'level': 1,    # Could be enhanced for sub-sections
            })
        
        return toc_items


class ExportHandler:
    """Handles document export to different formats"""
    
    def __init__(self, export_format: ExportFormat):
        self.export_format = export_format
    
    def export_document(self, html_content: str, job: ExportJob) -> bool:
        """Export document to the specified format"""
        try:
            if self.export_format.format_type == 'html':
                return self._export_html(html_content, job)
            elif self.export_format.format_type == 'pdf':
                return self._export_pdf(html_content, job)
            elif self.export_format.format_type == 'docx':
                return self._export_docx(html_content, job)
            elif self.export_format.format_type == 'txt':
                return self._export_txt(html_content, job)
            else:
                job.error_message = f"Unsupported format: {self.export_format.format_type}"
                return False
        except Exception as e:
            job.error_message = str(e)
            return False
    
    def _export_html(self, html_content: str, job: ExportJob) -> bool:
        """Export as HTML file"""
        # Add CSS styling
        styled_html = self._add_html_styling(html_content, job.assembly_config)
        
        # Create file
        filename = f"document_{job.job_id}.html"
        content_file = ContentFile(styled_html.encode('utf-8'))
        job.output_file.save(filename, content_file)
        job.file_size = len(styled_html.encode('utf-8'))
        
        return True
    
    def _export_pdf(self, html_content: str, job: ExportJob) -> bool:
        """Export as PDF file"""
        try:
            # This would require a PDF generation library like weasyprint or reportlab
            # For now, we'll create a placeholder
            styled_html = self._add_html_styling(html_content, job.assembly_config)
            
            # TODO: Implement actual PDF generation
            # For development, save as HTML with PDF extension
            filename = f"document_{job.job_id}.pdf"
            content_file = ContentFile(styled_html.encode('utf-8'))
            job.output_file.save(filename, content_file)
            job.file_size = len(styled_html.encode('utf-8'))
            
            return True
            
        except Exception as e:
            job.error_message = f"PDF export error: {str(e)}"
            return False
    
    def _export_docx(self, html_content: str, job: ExportJob) -> bool:
        """Export as Microsoft Word document"""
        try:
            # This would require a library like python-docx
            # For now, create a basic implementation
            
            # TODO: Implement actual DOCX generation
            # For development, save as HTML with DOCX extension
            styled_html = self._add_html_styling(html_content, job.assembly_config)
            filename = f"document_{job.job_id}.docx"
            content_file = ContentFile(styled_html.encode('utf-8'))
            job.output_file.save(filename, content_file)
            job.file_size = len(styled_html.encode('utf-8'))
            
            return True
            
        except Exception as e:
            job.error_message = f"DOCX export error: {str(e)}"
            return False
    
    def _export_txt(self, html_content: str, job: ExportJob) -> bool:
        """Export as plain text"""
        try:
            # Strip HTML tags for plain text
            import re
            text_content = re.sub(r'<[^>]+>', '', html_content)
            text_content = text_content.strip()
            
            filename = f"document_{job.job_id}.txt"
            content_file = ContentFile(text_content.encode('utf-8'))
            job.output_file.save(filename, content_file)
            job.file_size = len(text_content.encode('utf-8'))
            
            return True
            
        except Exception as e:
            job.error_message = f"TXT export error: {str(e)}"
            return False
    
    def _add_html_styling(self, html_content: str, assembly_config: AssemblyConfiguration) -> str:
        """Add CSS styling to HTML content"""
        css_styles = f"""
        <style>
        body {{
            font-family: '{assembly_config.font_family}', serif;
            font-size: {assembly_config.font_size}pt;
            line-height: {assembly_config.line_spacing};
            margin: {assembly_config.margin_top}in {assembly_config.margin_right}in {assembly_config.margin_bottom}in {assembly_config.margin_left}in;
            color: #000;
        }}
        
        .document-section {{
            margin-bottom: 2em;
        }}
        
        .section-header {{
            margin-bottom: 1em;
        }}
        
        .section-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin: 0;
            padding-bottom: 0.5em;
            border-bottom: 1px solid #ccc;
        }}
        
        .section-number {{
            margin-right: 0.5em;
        }}
        
        .section-content {{
            margin-top: 1em;
        }}
        
        .page-break {{
            page-break-before: always;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        
        @media print {{
            .page-break {{
                page-break-before: always;
            }}
        }}
        </style>
        """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{assembly_config.name}</title>
            {css_styles}
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """


class DocumentAssemblyService:
    """Service for managing document assembly operations"""
    
    @staticmethod
    def create_assembly_config(team, name: str, base_template: DocumentTemplate, 
                             sections: List[ProposalSection], created_by) -> AssemblyConfiguration:
        """Create a new assembly configuration"""
        config = AssemblyConfiguration.objects.create(
            team=team,
            name=name,
            base_template=base_template,
            created_by=created_by
        )
        
        # Add sections in order
        for i, section in enumerate(sections, 1):
            DocumentSection.objects.create(
                assembly_config=config,
                proposal_section=section,
                order=i
            )
        
        return config
    
    @staticmethod
    def create_export_job(assembly_config: AssemblyConfiguration, export_format: ExportFormat, 
                         requested_by, parameters: Dict = None) -> ExportJob:
        """Create a new export job"""
        job = ExportJob.objects.create(
            assembly_config=assembly_config,
            export_format=export_format,
            requested_by=requested_by,
            parameters=parameters or {}
        )
        
        # Start the export task
        export_document_task.delay(job.id)
        
        return job
    
    @staticmethod
    def get_default_template(template_type: str = 'proposal') -> Optional[DocumentTemplate]:
        """Get the default template for a type"""
        return DocumentTemplate.objects.filter(
            template_type=template_type,
            is_default=True,
            is_active=True
        ).first()
    
    @staticmethod
    def create_default_export_formats():
        """Create default export formats if they don't exist"""
        formats = [
            {
                'name': 'HTML Document',
                'format_type': 'html',
                'description': 'Standard HTML format with CSS styling',
                'settings': {'include_css': True, 'responsive': False}
            },
            {
                'name': 'PDF Document',
                'format_type': 'pdf',
                'description': 'Portable Document Format',
                'settings': {'page_size': 'letter', 'orientation': 'portrait'}
            },
            {
                'name': 'Microsoft Word',
                'format_type': 'docx',
                'description': 'Microsoft Word document format',
                'settings': {'compatibility_mode': 'word2016'}
            },
            {
                'name': 'Plain Text',
                'format_type': 'txt',
                'description': 'Plain text format',
                'settings': {'encoding': 'utf-8', 'line_endings': 'unix'}
            }
        ]
        
        for format_data in formats:
            ExportFormat.objects.get_or_create(
                format_type=format_data['format_type'],
                defaults=format_data
            )


@shared_task
def export_document_task(job_id: int):
    """Celery task for document export"""
    try:
        job = ExportJob.objects.get(id=job_id)
        job.status = 'processing'
        job.started_at = timezone.now()
        job.save()
        
        # Assemble the document
        engine = DocumentAssemblyEngine(job.assembly_config)
        html_content = engine.assemble_document()
        
        # Export to the requested format
        handler = ExportHandler(job.export_format)
        success = handler.export_document(html_content, job)
        
        if success:
            job.status = 'completed'
            job.progress_percentage = 100
        else:
            job.status = 'failed'
        
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        try:
            job = ExportJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()
        except:
            pass