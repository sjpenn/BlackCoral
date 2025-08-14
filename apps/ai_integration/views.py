from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .tasks import (
    analyze_opportunity_with_ai, 
    check_opportunity_compliance,
    generate_opportunity_content,
    test_ai_providers
)
from .models import AITask
from .ai_providers import ai_manager
from apps.opportunities.models import Opportunity


@login_required
def ai_dashboard(request):
    """
    AI integration dashboard with provider status and recent tasks.
    """
    # Handle HTMX requests for authenticated users
    if request.headers.get('HX-Request') and not request.user.is_authenticated:
        response = HttpResponse()
        response['HX-Redirect'] = '/auth/login/'
        return response
    
    # Get available AI providers
    available_providers = ai_manager.get_available_providers()
    model_info = ai_manager.get_model_info()
    
    # Get recent AI tasks
    recent_tasks = AITask.objects.all()[:10]
    
    # Get AI analysis statistics
    opportunities_analyzed = Opportunity.objects.filter(ai_analysis_complete=True).count()
    compliance_checked = Opportunity.objects.filter(compliance_checked=True).count()
    total_opportunities = Opportunity.objects.filter(is_active=True).count()
    
    context = {
        'page_title': 'AI Integration Dashboard',
        'available_providers': available_providers,
        'model_info': model_info,
        'recent_tasks': recent_tasks,
        'stats': {
            'opportunities_analyzed': opportunities_analyzed,
            'compliance_checked': compliance_checked,
            'total_opportunities': total_opportunities,
            'analysis_coverage': round((opportunities_analyzed / total_opportunities * 100) if total_opportunities > 0 else 0, 1)
        }
    }
    return render(request, 'ai_integration/dashboard.html', context)


@login_required
@require_POST
def analyze_opportunity(request, opportunity_id):
    """
    HTMX endpoint to trigger AI analysis of an opportunity.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    opportunity = get_object_or_404(Opportunity, id=opportunity_id, is_active=True)
    provider = request.POST.get('provider', None)
    
    # Check if analysis is already running
    existing_task = AITask.objects.filter(
        opportunity=opportunity,
        task_type='analyze_opportunity',
        status__in=['pending', 'processing']
    ).first()
    
    if existing_task:
        return JsonResponse({
            'status': 'already_running',
            'message': 'Analysis is already in progress for this opportunity'
        })
    
    # Trigger analysis task
    task = analyze_opportunity_with_ai.delay(opportunity_id, provider)
    
    # Create AI task record
    ai_task = AITask.objects.create(
        task_type='analyze_opportunity',
        opportunity=opportunity,
        input_data={
            'opportunity_id': opportunity_id,
            'provider': provider,
            'requested_by': request.user.id
        },
        ai_provider=provider or 'claude',
        status='pending'
    )
    
    return JsonResponse({
        'status': 'started',
        'task_id': task.id,
        'ai_task_id': ai_task.id,
        'message': f'AI analysis started for {opportunity.title}'
    })


@login_required
@require_POST
def check_compliance(request, opportunity_id):
    """
    HTMX endpoint to trigger AI compliance check.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    opportunity = get_object_or_404(Opportunity, id=opportunity_id, is_active=True)
    provider = request.POST.get('provider', None)
    
    # Trigger compliance check task
    task = check_opportunity_compliance.delay(opportunity_id, provider)
    
    # Create AI task record
    ai_task = AITask.objects.create(
        task_type='compliance_check',
        opportunity=opportunity,
        input_data={
            'opportunity_id': opportunity_id,
            'provider': provider,
            'requested_by': request.user.id
        },
        ai_provider=provider or 'claude',
        status='pending'
    )
    
    return JsonResponse({
        'status': 'started',
        'task_id': task.id,
        'ai_task_id': ai_task.id,
        'message': 'Compliance check started'
    })


@login_required
@require_POST
def generate_content(request, opportunity_id):
    """
    HTMX endpoint to generate AI content (proposal outlines, summaries).
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    opportunity = get_object_or_404(Opportunity, id=opportunity_id, is_active=True)
    content_type = request.POST.get('content_type', 'proposal_outline')
    provider = request.POST.get('provider', None)
    
    # Validate content type
    valid_content_types = ['proposal_outline', 'executive_summary']
    if content_type not in valid_content_types:
        return JsonResponse({'error': 'Invalid content type'}, status=400)
    
    # Trigger content generation task
    task = generate_opportunity_content.delay(opportunity_id, content_type, provider)
    
    # Create AI task record
    ai_task = AITask.objects.create(
        task_type='generate_content',
        opportunity=opportunity,
        input_data={
            'opportunity_id': opportunity_id,
            'content_type': content_type,
            'provider': provider,
            'requested_by': request.user.id
        },
        ai_provider=provider or 'claude',
        status='pending'
    )
    
    return JsonResponse({
        'status': 'started',
        'task_id': task.id,
        'ai_task_id': ai_task.id,
        'message': f'{content_type.replace("_", " ").title()} generation started'
    })


@login_required
def task_status(request, task_id):
    """
    HTMX endpoint to check AI task status.
    """
    try:
        task = AITask.objects.get(id=task_id)
        
        return JsonResponse({
            'status': task.status,
            'task_type': task.get_task_type_display(),
            'ai_provider': task.get_ai_provider_display(),
            'created_at': task.created_at.isoformat(),
            'error_message': task.error_message,
            'confidence_score': task.confidence_score,
            'tokens_used': task.tokens_used,
            'processing_time': task.processing_time
        })
        
    except AITask.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)


@login_required
def opportunity_ai_data(request, opportunity_id):
    """
    HTMX endpoint to get AI analysis data for an opportunity.
    """
    opportunity = get_object_or_404(Opportunity, id=opportunity_id, is_active=True)
    
    # Prepare AI data for template
    ai_data = {
        'analysis_complete': opportunity.ai_analysis_complete,
        'compliance_checked': opportunity.compliance_checked,
        'analysis_data': opportunity.ai_analysis_data,
        'compliance_data': opportunity.compliance_data,
        'generated_content': opportunity.generated_content
    }
    
    # Get recent AI tasks for this opportunity
    recent_tasks = AITask.objects.filter(
        opportunity=opportunity
    ).order_by('-created_at')[:5]
    
    context = {
        'opportunity': opportunity,
        'ai_data': ai_data,
        'recent_tasks': recent_tasks,
        'available_providers': ai_manager.get_available_providers()
    }
    
    return render(request, 'ai_integration/partials/opportunity_ai_data.html', context)


@login_required
@require_POST
def test_providers(request):
    """
    HTMX endpoint to test all AI providers.
    """
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Trigger test task
    task = test_ai_providers.delay()
    
    return JsonResponse({
        'status': 'started',
        'task_id': task.id,
        'message': 'Testing all AI providers...'
    })