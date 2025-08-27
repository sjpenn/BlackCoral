"""
BLACK CORAL Documents Views
Document assembly and export management views
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone

from apps.collaboration.models import ProposalTeam, ProposalSection
from apps.opportunities.models import Opportunity
from .models import (
    DocumentTemplate, AssemblyConfiguration, DocumentSection,
    DocumentVariable, ExportFormat, ExportJob, DocumentUpload
)
from .assembly_services import DocumentAssemblyService, DocumentAssemblyEngine
from .api_views_simple import list_documents as api_document_list


@login_required
def document_list(request):
    """
    List view for documents - placeholder for Phase 2.
    """
    # Handle HTMX requests for authenticated users
    if request.headers.get('HX-Request') and not request.user.is_authenticated:
        response = HttpResponse()
        response['HX-Redirect'] = '/auth/login/'
        return response
        
    context = {
        'page_title': 'Documents'
    }
    return render(request, 'documents/list.html', context)


@login_required
def assembly_list(request, team_id):
    """List all assembly configurations for a team"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    if not team.can_user_access(request.user):
        messages.error(request, "You don't have permission to access this team.")
        return redirect('collaboration:team_list')
    
    configs = team.assembly_configs.all().order_by('-is_default', 'name')
    
    context = {
        'team': team,
        'configs': configs,
        'can_manage': team.can_user_manage(request.user),
    }
    
    return render(request, 'documents/assembly_list.html', context)


@login_required
def assembly_detail(request, team_id, config_id):
    """View assembly configuration details"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    config = get_object_or_404(AssemblyConfiguration, id=config_id, team=team)
    
    # Check permissions
    if not team.can_user_access(request.user):
        messages.error(request, "You don't have permission to access this team.")
        return redirect('collaboration:team_list')
    
    # Get document sections in order
    document_sections = config.document_sections.all().order_by('order')
    
    # Get variables
    variables = config.variables.all().order_by('name')
    
    # Get recent export jobs
    recent_jobs = config.export_jobs.all()[:10]
    
    # Get available export formats
    export_formats = ExportFormat.objects.filter(is_active=True)
    
    context = {
        'team': team,
        'config': config,
        'document_sections': document_sections,
        'variables': variables,
        'recent_jobs': recent_jobs,
        'export_formats': export_formats,
        'can_manage': team.can_user_manage(request.user),
    }
    
    return render(request, 'documents/assembly_detail.html', context)


@login_required
def create_assembly(request, team_id):
    """Create a new assembly configuration"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    if not team.can_user_manage(request.user):
        messages.error(request, "You don't have permission to manage this team.")
        return redirect('collaboration:team_detail', team_id=team_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                name = request.POST.get('name')
                description = request.POST.get('description', '')
                
                # Get base template
                template_id = request.POST.get('base_template')
                base_template = get_object_or_404(DocumentTemplate, id=template_id)
                
                # Get selected sections
                section_ids = request.POST.getlist('sections')
                sections = ProposalSection.objects.filter(
                    id__in=section_ids, 
                    team=team
                )
                
                if not sections:
                    messages.error(request, "Please select at least one section.")
                    return redirect('documents:create_assembly', team_id=team_id)
                
                # Create assembly configuration
                config = DocumentAssemblyService.create_assembly_config(
                    team=team,
                    name=name,
                    base_template=base_template,
                    sections=list(sections),
                    created_by=request.user
                )
                
                config.description = description
                config.save()
                
                messages.success(request, f"Assembly configuration '{name}' created successfully.")
                return redirect('documents:assembly_detail', team_id=team_id, config_id=config.id)
                
        except Exception as e:
            messages.error(request, f"Error creating assembly configuration: {str(e)}")
    
    # Get available templates and sections
    templates = DocumentTemplate.objects.filter(
        template_type='proposal',
        is_active=True
    )
    sections = team.sections.all().order_by('section_number')
    
    context = {
        'team': team,
        'templates': templates,
        'sections': sections,
    }
    
    return render(request, 'documents/create_assembly.html', context)


@login_required
@require_POST
def export_document(request, team_id, config_id):
    """Start document export job"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    config = get_object_or_404(AssemblyConfiguration, id=config_id, team=team)
    
    # Check permissions
    if not team.can_user_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    try:
        # Get export format
        format_id = request.POST.get('format_id')
        export_format = get_object_or_404(ExportFormat, id=format_id, is_active=True)
        
        # Create export job
        job = DocumentAssemblyService.create_export_job(
            assembly_config=config,
            export_format=export_format,
            requested_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'job_id': job.id,
            'message': f'Export job started for {export_format.name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def download_export(request, team_id, job_id):
    """Download completed export file"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    job = get_object_or_404(ExportJob, id=job_id, assembly_config__team=team)
    
    # Check permissions
    if not team.can_user_access(request.user):
        messages.error(request, "You don't have permission to access this team.")
        return redirect('collaboration:team_list')
    
    # Check if job is completed and has output file
    if not job.is_complete or not job.output_file:
        messages.error(request, "Export file is not available.")
        return redirect('documents:assembly_detail', team_id=team_id, config_id=job.assembly_config.id)
    
    # Return file response
    try:
        response = FileResponse(
            job.output_file.open('rb'),
            as_attachment=True,
            filename=job.output_file.name.split('/')[-1]
        )
        return response
    except Exception as e:
        messages.error(request, f"Error downloading file: {str(e)}")
        return redirect('documents:assembly_detail', team_id=team_id, config_id=job.assembly_config.id)


@login_required
def preview_document(request, team_id, config_id):
    """Preview assembled document"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    config = get_object_or_404(AssemblyConfiguration, id=config_id, team=team)
    
    # Check permissions
    if not team.can_user_access(request.user):
        messages.error(request, "You don't have permission to access this team.")
        return redirect('collaboration:team_list')
    
    try:
        # Assemble document for preview
        engine = DocumentAssemblyEngine(config)
        html_content = engine.assemble_document()
        
        context = {
            'team': team,
            'config': config,
            'html_content': html_content,
            'variables': engine.variables,
        }
        
        return render(request, 'documents/document_preview.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating preview: {str(e)}")
        return redirect('documents:assembly_detail', team_id=team_id, config_id=config_id)


@login_required
@require_POST
def update_variable(request, team_id, config_id):
    """Update document variable value"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    config = get_object_or_404(AssemblyConfiguration, id=config_id, team=team)
    
    # Check permissions
    if not team.can_user_manage(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    try:
        variable_name = request.POST.get('name')
        variable_value = request.POST.get('value', '')
        
        # Update variable
        variable = config.variables.get(name=variable_name)
        variable.current_value = variable_value
        variable.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Variable {variable.display_name} updated'
        })
        
    except DocumentVariable.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Variable not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def export_status(request, team_id, job_id):
    """Get export job status"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    job = get_object_or_404(ExportJob, id=job_id, assembly_config__team=team)
    
    # Check permissions
    if not team.can_user_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    return JsonResponse({
        'success': True,
        'status': job.status,
        'progress': job.progress_percentage,
        'completed': job.is_complete,
        'error_message': job.error_message,
        'download_url': job.output_file.url if job.output_file else None,
    })


@login_required
def template_list(request):
    """List all document templates"""
    templates = DocumentTemplate.objects.filter(is_active=True).order_by('template_type', 'name')
    
    # Filter by type if specified
    template_type = request.GET.get('type')
    if template_type:
        templates = templates.filter(template_type=template_type)
    
    # Pagination
    paginator = Paginator(templates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'templates': page_obj,
        'template_types': DocumentTemplate.TEMPLATE_TYPE_CHOICES,
        'current_type': template_type,
    }
    
    return render(request, 'documents/template_list.html', context)


@login_required
def template_detail(request, template_id):
    """View template details"""
    template = get_object_or_404(DocumentTemplate, id=template_id, is_active=True)
    
    context = {
        'template': template,
    }
    
    return render(request, 'documents/template_detail.html', context)


@login_required
def jobs_list(request):
    """List user's export jobs"""
    jobs = ExportJob.objects.filter(requested_by=request.user).order_by('-created_at')
    
    # Filter by status if specified
    status = request.GET.get('status')
    if status:
        jobs = jobs.filter(status=status)
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'jobs': page_obj,
        'status_choices': ExportJob.STATUS_CHOICES,
        'current_status': status,
    }
    
    return render(request, 'documents/jobs_list.html', context)


@login_required
def upload_view(request):
    """Document upload interface"""
    # Get opportunities for the dropdown
    opportunities = Opportunity.objects.filter(
        # Only show active opportunities that user can access
        # Add more filters based on user permissions if needed
    ).order_by('-created_at')[:50]  # Limit to recent 50 opportunities
    
    context = {
        'opportunities': opportunities,
        'page_title': 'Upload Documents',
    }
    
    return render(request, 'documents/upload.html', context)


@login_required
def upload_status_view(request):
    """Upload status dashboard"""
    # Get user's recent uploads
    recent_uploads = DocumentUpload.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]  # Limit to recent 20 uploads for the initial view
    
    # Get opportunities for filtering
    opportunities = Opportunity.objects.filter(
        # Add opportunity filtering based on user permissions
    ).order_by('-created_at')[:50]
    
    context = {
        'recent_uploads': recent_uploads,
        'opportunities': opportunities,
        'page_title': 'Upload Status',
    }
    
    return render(request, 'documents/upload_status.html', context)