"""
Workflow and Approval Views for BLACK CORAL
Handles section workflow, reviews, and approvals
"""

import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import (
    ProposalTeam, ProposalSection, SectionReview, 
    SectionApproval, WorkflowTemplate
)
from .workflow_services import workflow_service, review_service, approval_service

User = get_user_model()


@login_required
def section_workflow(request, team_id, section_id):
    """Section workflow management page"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    # Get or create workflow instance
    try:
        workflow = section.workflow
    except:
        workflow = workflow_service.start_workflow(section)
    
    # Get reviews and approvals
    reviews = section.reviews.select_related('reviewer').order_by('-created_at')
    approvals = section.approvals.select_related('approver').order_by('approval_level')
    
    # Get workflow templates for team
    templates = WorkflowTemplate.objects.filter(team=team, is_active=True)
    
    context = {
        'team': team,
        'section': section,
        'workflow': workflow,
        'reviews': reviews,
        'approvals': approvals,
        'templates': templates,
        'can_manage': team.lead == request.user,
    }
    
    return render(request, 'collaboration/section_workflow.html', context)


@login_required
@require_http_methods(['POST'])
def start_section_workflow(request, team_id, section_id):
    """Start workflow for a section"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check permissions
    if not (team.lead == request.user or section.assigned_to == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        workflow = workflow_service.start_workflow(section)
        
        return JsonResponse({
            'success': True,
            'workflow_id': workflow.id,
            'status': workflow.status,
            'current_step': workflow.current_step,
            'progress': workflow.progress_percentage
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def advance_workflow(request, team_id, section_id):
    """Advance section workflow to next step"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check permissions
    if not (team.lead == request.user):
        return JsonResponse({'error': 'Only team lead can advance workflow'}, status=403)
    
    try:
        success = workflow_service.advance_workflow(section)
        
        if success:
            workflow = section.workflow
            return JsonResponse({
                'success': True,
                'status': workflow.status,
                'current_step': workflow.current_step,
                'progress': workflow.progress_percentage
            })
        else:
            return JsonResponse({
                'error': 'Cannot advance workflow - current step not complete'
            }, status=400)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def review_section(request, team_id, section_id, review_id):
    """Section review interface"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    review = get_object_or_404(SectionReview, id=review_id, section=section)
    
    # Check if user is the assigned reviewer
    if review.reviewer != request.user:
        messages.error(request, "You are not assigned to this review.")
        return redirect('collaboration:section_workflow', team_id=team_id, section_id=section_id)
    
    if request.method == 'POST':
        # Process review submission
        feedback = request.POST.get('feedback', '')
        recommendation = request.POST.get('recommendation', '')
        
        scores = {
            'technical_accuracy': request.POST.get('technical_accuracy'),
            'clarity_score': request.POST.get('clarity_score'),
            'compliance_score': request.POST.get('compliance_score'),
            'overall_quality': request.POST.get('overall_quality'),
        }
        
        # Convert scores to integers, handle empty values
        for key, value in scores.items():
            if value:
                try:
                    scores[key] = int(value)
                except ValueError:
                    scores[key] = None
            else:
                scores[key] = None
        
        review_service.complete_review(review, feedback, recommendation, scores)
        
        messages.success(request, 'Review completed successfully!')
        return redirect('collaboration:section_workflow', team_id=team_id, section_id=section_id)
    
    # Mark review as started if not already
    if review.status == 'assigned':
        review_service.start_review(review)
    
    context = {
        'team': team,
        'section': section,
        'review': review,
    }
    
    return render(request, 'collaboration/section_review.html', context)


@login_required
def approve_section(request, team_id, section_id, approval_id):
    """Section approval interface"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    approval = get_object_or_404(SectionApproval, id=approval_id, section=section)
    
    # Check if user is the assigned approver
    if approval.approver != request.user:
        messages.error(request, "You are not assigned to this approval.")
        return redirect('collaboration:section_workflow', team_id=team_id, section_id=section_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        comments = request.POST.get('comments', '')
        conditions = request.POST.get('conditions', '')
        
        if action == 'approve':
            approval_service.approve_section(approval, comments, conditions)
            messages.success(request, 'Section approved successfully!')
        elif action == 'reject':
            approval_service.reject_section(approval, comments)
            messages.success(request, 'Section rejected. Author has been notified.')
        
        return redirect('collaboration:section_workflow', team_id=team_id, section_id=section_id)
    
    context = {
        'team': team,
        'section': section,
        'approval': approval,
    }
    
    return render(request, 'collaboration/section_approval.html', context)


@login_required
def review_dashboard(request):
    """User's review dashboard"""
    dashboard_data = review_service.get_review_dashboard(request.user)
    
    context = {
        'dashboard_data': dashboard_data,
        'user': request.user,
    }
    
    return render(request, 'collaboration/review_dashboard.html', context)


@login_required
def approval_dashboard(request):
    """User's approval dashboard"""
    dashboard_data = approval_service.get_approval_dashboard(request.user)
    
    context = {
        'dashboard_data': dashboard_data,
        'user': request.user,
    }
    
    return render(request, 'collaboration/approval_dashboard.html', context)


@login_required
def workflow_templates(request, team_id):
    """Manage workflow templates for team"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    if team.lead != request.user:
        messages.error(request, "Only team lead can manage workflow templates.")
        return redirect('collaboration:team_detail', team_id=team_id)
    
    if request.method == 'POST':
        # Create default templates if none exist
        if not WorkflowTemplate.objects.filter(team=team).exists():
            created_templates = workflow_service.create_default_templates(team)
            messages.success(request, f'Created {len(created_templates)} default workflow templates.')
    
    templates = WorkflowTemplate.objects.filter(team=team).order_by('name')
    
    context = {
        'team': team,
        'templates': templates,
    }
    
    return render(request, 'collaboration/workflow_templates.html', context)


@login_required
@require_http_methods(['POST'])
def create_workflow_template(request, team_id):
    """Create new workflow template"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    if team.lead != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        section_types = request.POST.getlist('section_types')
        required_reviews = request.POST.getlist('required_reviews')
        approval_sequence = request.POST.getlist('approval_sequence')
        
        template = WorkflowTemplate.objects.create(
            team=team,
            name=name,
            description=description,
            section_types=section_types,
            required_reviews=required_reviews,
            approval_sequence=approval_sequence
        )
        
        if request.headers.get('HX-Request'):
            context = {'template': template, 'team': team}
            return render(request, 'collaboration/partials/workflow_template_item.html', context)
        
        messages.success(request, f'Workflow template "{name}" created successfully!')
        return redirect('collaboration:workflow_templates', team_id=team_id)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)