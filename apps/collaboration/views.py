"""
BLACK CORAL Team Collaboration Views
Team management, task assignment, and proposal workflow
"""

import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator

from .models import (
    ProposalTeam, TeamMembership, ProposalSection, TaskItem,
    TeamComment, ProposalMilestone, TimeLog
)
from apps.opportunities.models import Opportunity
from apps.notifications.services import notification_service

User = get_user_model()


@login_required
def team_list(request):
    """List all teams user is part of"""
    user_teams = ProposalTeam.objects.filter(
        Q(members=request.user) | Q(lead=request.user)
    ).distinct().select_related('opportunity', 'lead').prefetch_related('members')
    
    # Add team statistics
    teams_with_stats = []
    for team in user_teams:
        team_stats = {
            'team': team,
            'total_tasks': team.tasks.count(),
            'completed_tasks': team.tasks.filter(status='completed').count(),
            'overdue_tasks': team.tasks.filter(
                due_date__lt=timezone.now(),
                status__in=['todo', 'in_progress']
            ).count(),
            'team_size': team.members.count(),
            'progress_percentage': 0
        }
        
        if team_stats['total_tasks'] > 0:
            team_stats['progress_percentage'] = (
                team_stats['completed_tasks'] / team_stats['total_tasks']
            ) * 100
        
        teams_with_stats.append(team_stats)
    
    context = {
        'teams_with_stats': teams_with_stats,
        'user_role_counts': {
            'leading': user_teams.filter(lead=request.user).count(),
            'member': user_teams.filter(members=request.user).exclude(lead=request.user).count(),
        }
    }
    
    return render(request, 'collaboration/team_list.html', context)


@login_required
def team_detail(request, team_id):
    """Team dashboard with overview and quick actions"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check if user has access to this team
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    # Get user's membership info
    user_membership = TeamMembership.objects.filter(team=team, user=request.user).first()
    
    # Team statistics
    stats = {
        'total_tasks': team.tasks.count(),
        'completed_tasks': team.tasks.filter(status='completed').count(),
        'overdue_tasks': team.tasks.filter(
            due_date__lt=timezone.now(),
            status__in=['todo', 'in_progress']
        ).count(),
        'total_sections': team.sections.count(),
        'completed_sections': team.sections.filter(status='approved').count(),
        'total_hours_logged': team.time_logs.aggregate(
            total=Sum('hours')
        )['total'] or 0,
        'active_members': team.teammembership_set.filter(is_active=True).count(),
    }
    
    # Calculate progress percentage
    if stats['total_tasks'] > 0:
        stats['progress_percentage'] = (stats['completed_tasks'] / stats['total_tasks']) * 100
    else:
        stats['progress_percentage'] = 0
    
    # Recent activity
    recent_tasks = team.tasks.select_related('assigned_to').order_by('-updated_at')[:5]
    recent_comments = team.comments.select_related('author').order_by('-created_at')[:5]
    upcoming_milestones = team.milestones.filter(
        target_date__gte=timezone.now(),
        is_completed=False
    ).order_by('target_date')[:3]
    
    # Team members with their current workload
    members_workload = []
    memberships = team.teammembership_set.filter(is_active=True).select_related('user')
    for membership in memberships:
        active_tasks = team.tasks.filter(
            assigned_to=membership.user,
            status__in=['todo', 'in_progress']
        ).count()
        
        members_workload.append({
            'membership': membership,
            'active_tasks': active_tasks,
            'completion_rate': membership.completion_rate,
        })
    
    context = {
        'team': team,
        'user_membership': user_membership,
        'stats': stats,
        'recent_tasks': recent_tasks,
        'recent_comments': recent_comments,
        'upcoming_milestones': upcoming_milestones,
        'members_workload': members_workload,
        'can_manage': team.lead == request.user or (
            user_membership and user_membership.role in ['lead', 'proposal_manager']
        )
    }
    
    return render(request, 'collaboration/team_detail.html', context)


@login_required
def team_tasks(request, team_id):
    """Task management interface"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    # Filter and sort tasks
    tasks_queryset = team.tasks.select_related('assigned_to', 'section').order_by('-priority', 'due_date')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        tasks_queryset = tasks_queryset.filter(status=status_filter)
    
    assigned_filter = request.GET.get('assigned')
    if assigned_filter:
        tasks_queryset = tasks_queryset.filter(assigned_to_id=assigned_filter)
    
    priority_filter = request.GET.get('priority')
    if priority_filter:
        tasks_queryset = tasks_queryset.filter(priority=priority_filter)
    
    # Pagination
    paginator = Paginator(tasks_queryset, 20)
    page_number = request.GET.get('page')
    tasks = paginator.get_page(page_number)
    
    # Get team members for assignment dropdown
    team_members = User.objects.filter(
        teammembership__team=team,
        teammembership__is_active=True
    ).distinct()
    
    context = {
        'team': team,
        'tasks': tasks,
        'team_members': team_members,
        'status_choices': TaskItem.TASK_STATUS_CHOICES,
        'priority_choices': TaskItem.PRIORITY_CHOICES,
        'current_filters': {
            'status': status_filter,
            'assigned': assigned_filter,
            'priority': priority_filter,
        }
    }
    
    return render(request, 'collaboration/team_tasks.html', context)


@login_required
@require_http_methods(['POST'])
def create_task(request, team_id):
    """Create a new task"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    user_membership = TeamMembership.objects.filter(team=team, user=request.user).first()
    if not (team.lead == request.user or (user_membership and user_membership.role in ['lead', 'proposal_manager'])):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Extract data
    title = request.POST.get('title')
    description = request.POST.get('description', '')
    task_type = request.POST.get('task_type', 'other')
    assigned_to_id = request.POST.get('assigned_to')
    section_id = request.POST.get('section')
    priority = request.POST.get('priority', 'medium')
    due_date = request.POST.get('due_date')
    estimated_hours = float(request.POST.get('estimated_hours', 0))
    
    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)
    
    # Create task
    task = TaskItem.objects.create(
        team=team,
        title=title,
        description=description,
        task_type=task_type,
        priority=priority,
        estimated_hours=estimated_hours,
        created_by=request.user
    )
    
    # Set optional fields
    if assigned_to_id:
        try:
            assigned_user = User.objects.get(id=assigned_to_id)
            if team.members.filter(id=assigned_user.id).exists():
                task.assigned_to = assigned_user
        except User.DoesNotExist:
            pass
    
    if section_id:
        try:
            section = ProposalSection.objects.get(id=section_id, team=team)
            task.section = section
        except ProposalSection.DoesNotExist:
            pass
    
    if due_date:
        try:
            task.due_date = datetime.strptime(due_date, '%Y-%m-%d')
        except ValueError:
            pass
    
    task.save()
    
    # Send notification to assigned user
    if task.assigned_to and task.assigned_to != request.user:
        notification_service.create_notification(
            user=task.assigned_to,
            notification_type='task_assigned',
            title=f"New task assigned: {task.title}",
            message=f"You've been assigned a new {task.get_task_type_display().lower()} task for {team.name}",
            content_object=task,
            action_url=f"/teams/{team.id}/tasks/",
            action_label="View Task",
            priority='high' if task.priority in ['high', 'critical'] else 'medium'
        )
    
    if request.headers.get('HX-Request'):
        # Return task item HTML for HTMX
        context = {'task': task, 'team': team}
        return render(request, 'collaboration/partials/task_item.html', context)
    
    messages.success(request, f'Task "{task.title}" created successfully!')
    return redirect('collaboration:team_tasks', team_id=team.id)


@login_required
@require_http_methods(['POST'])
def update_task_status(request, team_id, task_id):
    """Update task status via HTMX"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    task = get_object_or_404(TaskItem, id=task_id, team=team)
    
    # Check if user can update this task
    if not (task.assigned_to == request.user or team.lead == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    new_status = request.POST.get('status')
    if new_status not in [choice[0] for choice in TaskItem.TASK_STATUS_CHOICES]:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    old_status = task.status
    task.status = new_status
    
    if new_status == 'completed' and old_status != 'completed':
        task.completed_at = timezone.now()
        # Update member stats
        if task.assigned_to:
            membership = TeamMembership.objects.filter(
                team=team, user=task.assigned_to
            ).first()
            if membership:
                membership.tasks_completed += 1
                membership.save()
    
    task.save()
    
    if request.headers.get('HX-Request'):
        context = {'task': task, 'team': team}
        return render(request, 'collaboration/partials/task_item.html', context)
    
    return JsonResponse({'success': True})


@login_required
def team_sections(request, team_id):
    """Proposal sections management"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    sections = team.sections.select_related('assigned_to').order_by('section_number')
    
    # Calculate section statistics
    sections_with_stats = []
    for section in sections:
        section_tasks = section.tasks.all()
        completed_tasks = section_tasks.filter(status='completed').count()
        total_tasks = section_tasks.count()
        
        progress = 0
        if total_tasks > 0:
            progress = (completed_tasks / total_tasks) * 100
        
        sections_with_stats.append({
            'section': section,
            'task_progress': progress,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
        })
    
    # Team members for assignment
    team_members = User.objects.filter(
        teammembership__team=team,
        teammembership__is_active=True
    ).distinct()
    
    context = {
        'team': team,
        'sections_with_stats': sections_with_stats,
        'team_members': team_members,
        'can_manage': team.lead == request.user
    }
    
    return render(request, 'collaboration/team_sections.html', context)


@login_required
@require_http_methods(['POST'])
def create_section(request, team_id):
    """Create a new proposal section"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    if team.lead != request.user:
        return JsonResponse({'error': 'Only team lead can create sections'}, status=403)
    
    title = request.POST.get('title')
    section_number = request.POST.get('section_number')
    description = request.POST.get('description', '')
    assigned_to_id = request.POST.get('assigned_to')
    word_count_target = request.POST.get('word_count_target')
    due_date = request.POST.get('due_date')
    
    if not title or not section_number:
        return JsonResponse({'error': 'Title and section number are required'}, status=400)
    
    section = ProposalSection.objects.create(
        team=team,
        title=title,
        section_number=section_number,
        description=description
    )
    
    # Set optional fields
    if assigned_to_id:
        try:
            assigned_user = User.objects.get(id=assigned_to_id)
            if team.members.filter(id=assigned_user.id).exists():
                section.assigned_to = assigned_user
        except User.DoesNotExist:
            pass
    
    if word_count_target:
        try:
            section.word_count_target = int(word_count_target)
        except ValueError:
            pass
    
    if due_date:
        try:
            section.due_date = datetime.strptime(due_date, '%Y-%m-%d')
        except ValueError:
            pass
    
    section.save()
    
    # Send notification to assigned user
    if section.assigned_to and section.assigned_to != request.user:
        notification_service.create_notification(
            user=section.assigned_to,
            notification_type='task_assigned',
            title=f"Section assigned: {section.title}",
            message=f"You've been assigned to write section {section.section_number}: {section.title}",
            content_object=section,
            action_url=f"/teams/{team.id}/sections/",
            action_label="View Section",
            priority='high'
        )
    
    if request.headers.get('HX-Request'):
        context = {'section': section, 'team': team}
        return render(request, 'collaboration/partials/section_item.html', context)
    
    messages.success(request, f'Section "{section.title}" created successfully!')
    return redirect('collaboration:team_sections', team_id=team.id)


@login_required
def team_comments(request, team_id):
    """Team communication and comments"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    # Get comments with threading
    comments = team.comments.filter(parent_comment__isnull=True).select_related(
        'author', 'task', 'section'
    ).prefetch_related(
        'replies__author', 'mentioned_users'
    ).order_by('-created_at')
    
    # Filter by type if specified
    comment_type = request.GET.get('type')
    if comment_type:
        comments = comments.filter(comment_type=comment_type)
    
    # Pagination
    paginator = Paginator(comments, 10)
    page_number = request.GET.get('page')
    comments_page = paginator.get_page(page_number)
    
    # Get team members for mentions
    team_members = User.objects.filter(
        teammembership__team=team,
        teammembership__is_active=True
    ).distinct()
    
    context = {
        'team': team,
        'comments': comments_page,
        'team_members': team_members,
        'comment_type_choices': TeamComment.COMMENT_TYPE_CHOICES,
        'current_type': comment_type,
    }
    
    return render(request, 'collaboration/team_comments.html', context)


@login_required
@require_http_methods(['POST'])
def create_comment(request, team_id):
    """Create a new team comment"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    content = request.POST.get('content')
    comment_type = request.POST.get('comment_type', 'general')
    subject = request.POST.get('subject', '')
    parent_id = request.POST.get('parent_comment')
    task_id = request.POST.get('task')
    section_id = request.POST.get('section')
    mentioned_user_ids = request.POST.getlist('mentioned_users')
    
    if not content:
        return JsonResponse({'error': 'Content is required'}, status=400)
    
    comment = TeamComment.objects.create(
        team=team,
        author=request.user,
        content=content,
        comment_type=comment_type,
        subject=subject
    )
    
    # Set optional relationships
    if parent_id:
        try:
            parent = TeamComment.objects.get(id=parent_id, team=team)
            comment.parent_comment = parent
        except TeamComment.DoesNotExist:
            pass
    
    if task_id:
        try:
            task = TaskItem.objects.get(id=task_id, team=team)
            comment.task = task
        except TaskItem.DoesNotExist:
            pass
    
    if section_id:
        try:
            section = ProposalSection.objects.get(id=section_id, team=team)
            comment.section = section
        except ProposalSection.DoesNotExist:
            pass
    
    comment.save()
    
    # Add mentioned users
    if mentioned_user_ids:
        mentioned_users = User.objects.filter(
            id__in=mentioned_user_ids,
            teammembership__team=team
        )
        comment.mentioned_users.set(mentioned_users)
    
    if request.headers.get('HX-Request'):
        context = {'comment': comment, 'team': team}
        return render(request, 'collaboration/partials/comment_item.html', context)
    
    messages.success(request, 'Comment posted successfully!')
    return redirect('collaboration:team_comments', team_id=team.id)


@login_required
def team_milestones(request, team_id):
    """Team milestones and deadlines"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    milestones = team.milestones.select_related('responsible_person').order_by('target_date')
    
    # Separate into completed and upcoming
    completed_milestones = milestones.filter(is_completed=True)
    upcoming_milestones = milestones.filter(is_completed=False)
    
    context = {
        'team': team,
        'completed_milestones': completed_milestones,
        'upcoming_milestones': upcoming_milestones,
        'can_manage': team.lead == request.user,
        'team_members': User.objects.filter(
            teammembership__team=team,
            teammembership__is_active=True
        ).distinct()
    }
    
    return render(request, 'collaboration/team_milestones.html', context)


@login_required
def team_analytics(request, team_id):
    """Team analytics and progress tracking"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    # Time period for analytics
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Task completion over time
    task_completion_data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        completed_count = team.tasks.filter(
            completed_at__date=date.date()
        ).count()
        task_completion_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'completed': completed_count
        })
    
    # Member productivity
    member_stats = []
    memberships = team.teammembership_set.filter(is_active=True).select_related('user')
    for membership in memberships:
        user_tasks = team.tasks.filter(assigned_to=membership.user)
        completed_tasks = user_tasks.filter(status='completed').count()
        total_tasks = user_tasks.count()
        # Calculate average completion time (simplified)
        completed_tasks_with_times = user_tasks.filter(
            completed_at__isnull=False,
            started_at__isnull=False
        )
        
        member_stats.append({
            'user': membership.user,
            'role': membership.get_role_display(),
            'completed_tasks': completed_tasks,
            'total_tasks': total_tasks,
            'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'hours_logged': team.time_logs.filter(user=membership.user).aggregate(
                total=Sum('hours')
            )['total'] or 0
        })
    
    context = {
        'team': team,
        'task_completion_data': task_completion_data,
        'member_stats': member_stats,
        'days': days,
        'total_tasks': team.tasks.count(),
        'completed_tasks': team.tasks.filter(status='completed').count(),
        'total_hours': team.time_logs.aggregate(total=Sum('hours'))['total'] or 0,
    }
    
    return render(request, 'collaboration/team_analytics.html', context)


# HTMX endpoints for real-time updates

@login_required
def team_dashboard_htmx(request, team_id):
    """HTMX endpoint for team dashboard updates"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Quick stats for dashboard
    stats = {
        'active_tasks': team.tasks.filter(status__in=['todo', 'in_progress']).count(),
        'overdue_tasks': team.tasks.filter(
            due_date__lt=timezone.now(),
            status__in=['todo', 'in_progress']
        ).count(),
        'completed_today': team.tasks.filter(
            completed_at__date=timezone.now().date()
        ).count(),
        'team_online': team.members.filter(
            last_activity__gte=timezone.now() - timedelta(minutes=15)
        ).count(),
    }
    
    context = {'team': team, 'stats': stats}
    return render(request, 'collaboration/partials/dashboard_stats.html', context)


@login_required
def task_quick_actions_htmx(request, team_id, task_id):
    """HTMX endpoint for task quick actions"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    task = get_object_or_404(TaskItem, id=task_id, team=team)
    
    context = {'task': task, 'team': team}
    return render(request, 'collaboration/partials/task_quick_actions.html', context)