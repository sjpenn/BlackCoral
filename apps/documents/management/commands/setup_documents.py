"""
Setup Documents Management Command
Creates default document templates and export formats
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.documents.models import DocumentTemplate, ExportFormat
from apps.documents.assembly_services import DocumentAssemblyService


class Command(BaseCommand):
    help = 'Setup default document templates and export formats'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up documents system...'))
        
        with transaction.atomic():
            # Create default document templates
            self._create_default_templates()
            
            # Create default export formats
            self._create_export_formats()
        
        self.stdout.write(self.style.SUCCESS('Documents system setup complete!'))
    
    def _create_default_templates(self):
        """Create default document templates"""
        self.stdout.write('Creating default document templates...')
        
        # Proposal Template
        proposal_template_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{{ variables.proposal_title|default:"Proposal" }}</title>
        </head>
        <body>
            {% if config.include_cover_page %}
            <div class="cover-page">
                <h1>{{ variables.proposal_title|default:"Government Proposal" }}</h1>
                <h2>{{ variables.solicitation_number|default:"" }}</h2>
                <div class="company-info">
                    <h3>{{ variables.company_name|default:"Your Company" }}</h3>
                    <p>{{ variables.company_address|default:"" }}</p>
                    <p>{{ variables.company_phone|default:"" }}</p>
                    <p>{{ variables.company_email|default:"" }}</p>
                </div>
                <div class="submission-info">
                    <p>Submitted: {{ assembly_date|date:"F j, Y" }}</p>
                    <p>Due Date: {{ variables.due_date|default:"" }}</p>
                </div>
            </div>
            <div class="page-break"></div>
            {% endif %}
            
            {% if config.include_table_of_contents %}
            <div class="table-of-contents">
                <h2>Table of Contents</h2>
                <!-- TOC will be generated automatically -->
            </div>
            <div class="page-break"></div>
            {% endif %}
            
            {% if config.include_executive_summary %}
            <div class="executive-summary">
                <h2>Executive Summary</h2>
                <p>{{ variables.executive_summary|default:"Executive summary content goes here." }}</p>
            </div>
            <div class="page-break"></div>
            {% endif %}
            
            <div class="proposal-sections">
                {% for section in sections %}
                    {{ section|safe }}
                {% endfor %}
            </div>
            
            {% if config.include_appendices %}
            <div class="appendices">
                <h2>Appendices</h2>
                <p>{{ variables.appendices|default:"Additional supporting materials." }}</p>
            </div>
            {% endif %}
        </body>
        </html>
        """
        
        proposal_variables = {
            'proposal_title': 'Proposal Title',
            'solicitation_number': 'Solicitation Number',
            'company_name': 'Company Name',
            'company_address': 'Company Address',
            'company_phone': 'Company Phone',
            'company_email': 'Company Email',
            'due_date': 'Proposal Due Date',
            'executive_summary': 'Executive Summary Content',
            'appendices': 'Appendices Content'
        }
        
        template, created = DocumentTemplate.objects.get_or_create(
            name='Standard Proposal Template',
            template_type='proposal',
            defaults={
                'description': 'Standard template for government proposals with cover page, TOC, and sections',
                'content_template': proposal_template_content,
                'variables': proposal_variables,
                'is_default': True,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(f'  ✓ Created: {template.name}')
        else:
            self.stdout.write(f'  - Exists: {template.name}')
        
        # Section Template
        section_template_content = """
        <div class="proposal-section">
            <h3>{{ section_title }}</h3>
            <div class="section-content">
                {{ section_content|safe }}
            </div>
        </div>
        """
        
        section_template, created = DocumentTemplate.objects.get_or_create(
            name='Standard Section Template',
            template_type='section',
            defaults={
                'description': 'Basic template for individual proposal sections',
                'content_template': section_template_content,
                'variables': {'section_title': 'Section Title', 'section_content': 'Section Content'},
                'is_default': True,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(f'  ✓ Created: {section_template.name}')
        else:
            self.stdout.write(f'  - Exists: {section_template.name}')
        
        # Cover Page Template
        cover_template_content = """
        <div class="cover-page">
            <div class="header">
                <h1>{{ variables.document_title|default:"Government Proposal" }}</h1>
                <h2>{{ variables.solicitation_number|default:"" }}</h2>
            </div>
            
            <div class="company-section">
                <h3>Submitted by:</h3>
                <div class="company-details">
                    <h4>{{ variables.company_name|default:"Your Company" }}</h4>
                    <p>{{ variables.company_address|default:"" }}</p>
                    <p>Phone: {{ variables.company_phone|default:"" }}</p>
                    <p>Email: {{ variables.company_email|default:"" }}</p>
                    <p>DUNS: {{ variables.duns_number|default:"" }}</p>
                    <p>CAGE Code: {{ variables.cage_code|default:"" }}</p>
                </div>
            </div>
            
            <div class="submission-details">
                <h3>Submission Details:</h3>
                <p>Submitted: {{ assembly_date|date:"F j, Y" }}</p>
                <p>Due Date: {{ variables.due_date|default:"" }}</p>
                <p>Point of Contact: {{ variables.poc_name|default:"" }}</p>
                <p>POC Phone: {{ variables.poc_phone|default:"" }}</p>
                <p>POC Email: {{ variables.poc_email|default:"" }}</p>
            </div>
        </div>
        """
        
        cover_variables = {
            'document_title': 'Document Title',
            'solicitation_number': 'Solicitation Number',
            'company_name': 'Company Name',
            'company_address': 'Company Address',
            'company_phone': 'Company Phone',
            'company_email': 'Company Email',
            'duns_number': 'DUNS Number',
            'cage_code': 'CAGE Code',
            'due_date': 'Due Date',
            'poc_name': 'Point of Contact Name',
            'poc_phone': 'POC Phone',
            'poc_email': 'POC Email'
        }
        
        cover_template, created = DocumentTemplate.objects.get_or_create(
            name='Government Proposal Cover Page',
            template_type='cover_page',
            defaults={
                'description': 'Professional cover page for government proposals',
                'content_template': cover_template_content,
                'variables': cover_variables,
                'is_default': True,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(f'  ✓ Created: {cover_template.name}')
        else:
            self.stdout.write(f'  - Exists: {cover_template.name}')
    
    def _create_export_formats(self):
        """Create default export formats"""
        self.stdout.write('Creating default export formats...')
        
        DocumentAssemblyService.create_default_export_formats()
        
        formats = ExportFormat.objects.all()
        for format_obj in formats:
            self.stdout.write(f'  ✓ Format: {format_obj.name} ({format_obj.format_type})')