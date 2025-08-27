"""
BLACK CORAL Team Collaboration Views
Team management, task assignment, and proposal workflow
"""

import json
import hashlib
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator

from .models import (
    ProposalTeam, TeamMembership, ProposalSection, TaskItem,
    TeamComment, ProposalMilestone, TimeLog, InlineComment,
    ReviewSession, ReviewParticipant, ReviewTemplate, CommentThread, VersionSnapshot
)
from apps.opportunities.models import Opportunity
from apps.notifications.services import notification_service
from .ai_services import section_ai_enhancer
from .workflow_services import workflow_service, review_service, approval_service
from .models import SectionReview, SectionApproval, WorkflowTemplate

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
def section_editor(request, team_id, section_id):
    """Rich text section editor with inline commenting and collaboration features"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        messages.error(request, "You don't have access to this team.")
        return redirect('collaboration:team_list')
    
    # Get inline comments for this section
    inline_comments = section.inline_comments.filter(status='active').select_related(
        'author', 'assigned_to', 'resolved_by'
    ).prefetch_related('mentioned_users', 'replies')
    
    # Get review sessions
    review_sessions = section.review_sessions.filter(
        status__in=['scheduled', 'in_progress']
    ).select_related('moderator')
    
    # Get version history
    version_snapshots = section.version_snapshots.all()[:10]  # Latest 10 versions
    
    # Get available reviewers (team members)
    available_reviewers = team.members.exclude(id=request.user.id)
    
    context = {
        'team': team,
        'section': section,
        'inline_comments': inline_comments,
        'review_sessions': review_sessions,
        'version_snapshots': version_snapshots,
        'available_reviewers': available_reviewers,
        'can_edit': section.assigned_to == request.user or team.lead == request.user,
        'current_user': request.user,
    }
    
    return render(request, 'collaboration/section_editor.html', context)


@login_required
@require_http_methods(['POST'])
def save_section_content(request, team_id, section_id):
    """Save section content with version tracking"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check edit permissions
    can_edit = (
        request.user == section.assigned_to or
        request.user == team.lead or
        team.members.filter(id=request.user.id, teammembership__role__in=['writer', 'editor']).exists()
    )
    
    if not can_edit:
        return JsonResponse({'error': 'Edit permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        new_content = data.get('content', '')
        change_summary = data.get('change_summary', '')
        
        # Check if content actually changed
        if new_content == section.content:
            return JsonResponse({'success': True, 'message': 'No changes detected'})
        
        # Create version snapshot of current content before updating
        current_hash = hashlib.sha256(section.content.encode()).hexdigest()
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        
        # Get next version number
        last_version = section.version_snapshots.first()
        if last_version:
            version_parts = last_version.version_number.split('.')
            major, minor = int(version_parts[0]), int(version_parts[1]) if len(version_parts) > 1 else 0
            if data.get('major_change', False):
                version_number = f"{major + 1}.0"
            else:
                version_number = f"{major}.{minor + 1}"
        else:
            version_number = "1.0"
        
        # Create version snapshot
        VersionSnapshot.objects.create(
            section=section,
            version_number=version_number,
            content_hash=new_hash,
            content=new_content,
            created_by=request.user,
            change_summary=change_summary,
            change_type=data.get('change_type', 'minor_edit'),
            word_count=len(new_content.split()),
            character_count=len(new_content),
        )
        
        # Update section
        section.content = new_content
        section.word_count_current = len(new_content.split())
        section.last_modified_by = request.user
        section.last_modified_at = timezone.now()
        
        # Update status if this is the first content
        if section.status == 'not_started' and new_content.strip():
            section.status = 'in_progress'
        
        section.save()
        
        # Check if any inline comments are now outdated
        outdated_comments = []
        for comment in section.inline_comments.filter(status='active'):
            if comment.check_if_outdated(new_hash):
                outdated_comments.append(comment.id)
        
        return JsonResponse({
            'success': True,
            'version_number': version_number,
            'word_count': section.word_count_current,
            'outdated_comments': outdated_comments,
            'last_modified': section.last_modified_at.isoformat(),
            'status': section.status
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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


# AI Enhancement endpoints

@login_required
@require_http_methods(['POST'])
def ai_enhance_section(request, team_id, section_id):
    """AI-powered section enhancement"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        enhancement_type = data.get('type', 'improve')
        content = data.get('content', section.content)
        
        # Get AI enhancement
        result = section_ai_enhancer.enhance_content(
            content=content,
            section_title=section.title,
            requirements=section.requirements,
            enhancement_type=enhancement_type
        )
        
        if 'error' in result:
            return JsonResponse(result, status=400)
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def ai_generate_outline(request, team_id, section_id):
    """Generate section outline using AI"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        result = section_ai_enhancer.generate_outline(
            section_title=section.title,
            requirements=section.requirements,
            word_count_target=section.word_count_target
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def ai_check_compliance(request, team_id, section_id):
    """AI compliance check for section"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        content = data.get('content', section.content)
        
        result = section_ai_enhancer.check_compliance(
            content=content,
            section_title=section.title,
            requirements=section.requirements
        )
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def ai_suggest_improvements(request, team_id, section_id):
    """Get AI improvement suggestions"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        content = data.get('content', section.content)
        word_count = data.get('word_count', 0)
        
        result = section_ai_enhancer.suggest_improvements(
            content=content,
            section_title=section.title,
            word_count_current=word_count,
            word_count_target=section.word_count_target
        )
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def ai_expand_content(request, team_id, section_id):
    """AI content expansion"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    section = get_object_or_404(ProposalSection, id=section_id, team=team)
    
    # Check access
    if not (team.members.filter(id=request.user.id).exists() or team.lead == request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        content = data.get('content', section.content)
        focus_area = data.get('focus_area', '')
        
        result = section_ai_enhancer.expand_content(
            content=content,
            section_title=section.title,
            target_expansion=focus_area
        )
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def team_documents(request, team_id):
    """Team documents management view - redirect to documents app"""
    team = get_object_or_404(ProposalTeam, id=team_id)
    
    # Check permissions
    if not team.can_user_access(request.user):
        messages.error(request, "You don't have permission to access this team.")
        return redirect('collaboration:team_list')
    
    # Redirect to documents assembly list
    return redirect('documents:assembly_list', team_id=team_id)


# Inline Commenting and Review Views

@login_required
@require_POST
def add_inline_comment(request, section_id):
    """Add an inline comment to a section"""
    section = get_object_or_404(ProposalSection, id=section_id)
    
    # Check access
    if not section.team.members.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # Create content hash for version tracking
        content_hash = hashlib.sha256(section.content.encode()).hexdigest()
        
        # Create inline comment
        comment = InlineComment.objects.create(
            section=section,
            author=request.user,
            comment_type=data.get('comment_type', 'suggestion'),
            urgency=data.get('urgency', 'medium'),
            text_selection=data.get('text_selection', ''),
            selection_start=int(data.get('selection_start', 0)),
            selection_end=int(data.get('selection_end', 0)),
            selection_context=data.get('selection_context', ''),
            content=data.get('content', ''),
            suggested_change=data.get('suggested_change', ''),
            section_version_hash=content_hash,
        )
        
        # Handle mentions
        mentioned_usernames = data.get('mentioned_users', [])
        if mentioned_usernames:
            mentioned_users = section.team.members.filter(
                username__in=mentioned_usernames
            )
            comment.mentioned_users.set(mentioned_users)
        
        # Handle assignment
        if data.get('assigned_to'):
            try:
                assigned_user = section.team.members.get(id=data['assigned_to'])
                comment.assigned_to = assigned_user
                comment.save()
            except:
                pass  # Invalid user ID
        
        # Create comment thread
        thread = CommentThread.objects.create(
            section=section,
            inline_comment=comment,
            title=f"{comment.get_comment_type_display()} on {section.title}"
        )
        thread.participants.add(request.user)
        if comment.assigned_to:
            thread.participants.add(comment.assigned_to)
        
        # Return comment data
        response_data = {
            'id': comment.id,
            'comment_type': comment.get_comment_type_display(),
            'urgency': comment.get_urgency_display(),
            'author': comment.author.get_full_name(),
            'content': comment.content,
            'suggested_change': comment.suggested_change,
            'created_at': comment.created_at.isoformat(),
            'selection_start': comment.selection_start,
            'selection_end': comment.selection_end,
            'thread_id': thread.id,
        }
        
        return JsonResponse({'success': True, 'comment': response_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def reply_to_comment(request, comment_id):
    """Reply to an inline comment"""
    parent_comment = get_object_or_404(InlineComment, id=comment_id)
    
    # Check access
    if not parent_comment.section.team.members.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # Create reply comment
        reply = InlineComment.objects.create(
            section=parent_comment.section,
            author=request.user,
            parent_comment=parent_comment,
            comment_type='reply',
            content=data.get('content', ''),
            section_version_hash=parent_comment.section_version_hash,
            text_selection=parent_comment.text_selection,
            selection_start=parent_comment.selection_start,
            selection_end=parent_comment.selection_end,
        )
        
        # Add to thread
        if hasattr(parent_comment, 'thread'):
            thread = parent_comment.thread
            thread.participants.add(request.user)
            thread.message_count += 1
            thread.save()
        
        response_data = {
            'id': reply.id,
            'author': reply.author.get_full_name(),
            'content': reply.content,
            'created_at': reply.created_at.isoformat(),
            'parent_id': parent_comment.id,
        }
        
        return JsonResponse({'success': True, 'reply': response_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def resolve_comment(request, comment_id):
    """Resolve an inline comment"""
    comment = get_object_or_404(InlineComment, id=comment_id)
    
    # Check permissions
    can_resolve = (
        request.user == comment.author or
        request.user == comment.assigned_to or
        request.user == comment.section.assigned_to or
        request.user == comment.section.team.lead
    )
    
    if not can_resolve:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        resolution_note = data.get('resolution_note', '')
        
        comment.resolve(request.user, resolution_note)
        
        # Resolve associated thread
        if hasattr(comment, 'thread'):
            comment.thread.resolve_thread(request.user, resolution_note)
        
        return JsonResponse({
            'success': True,
            'resolved_at': comment.resolved_at.isoformat(),
            'resolved_by': comment.resolved_by.get_full_name(),
            'resolution_note': comment.resolution_note
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def section_comments(request, section_id):
    """Get all comments for a section (HTMX endpoint)"""
    section = get_object_or_404(ProposalSection, id=section_id)
    
    # Check access
    if not section.team.members.filter(id=request.user.id).exists():
        return HttpResponse(status=403)
    
    # Get comments with filters
    status_filter = request.GET.get('status', 'active')
    comment_type = request.GET.get('type', '')
    urgency = request.GET.get('urgency', '')
    
    comments = section.inline_comments.select_related(
        'author', 'assigned_to', 'resolved_by'
    ).prefetch_related('mentioned_users', 'replies')
    
    if status_filter != 'all':
        comments = comments.filter(status=status_filter)
    if comment_type:
        comments = comments.filter(comment_type=comment_type)
    if urgency:
        comments = comments.filter(urgency=urgency)
    
    # Only show parent comments (not replies)
    comments = comments.filter(parent_comment__isnull=True)
    
    context = {
        'section': section,
        'comments': comments,
        'current_user': request.user,
    }
    
    return render(request, 'collaboration/partials/comment_list.html', context)


@login_required
def create_review_session(request, section_id):
    """Create a new review session"""
    section = get_object_or_404(ProposalSection, id=section_id)
    
    # Check permissions
    can_create = (
        request.user == section.team.lead or
        request.user == section.team.proposal_manager or
        request.user == section.assigned_to
    )
    
    if not can_create:
        messages.error(request, "You don't have permission to create review sessions.")
        return redirect('collaboration:section_editor', team_id=section.team.id, section_id=section_id)
    
    if request.method == 'POST':
        try:
            # Parse form data
            session_type = request.POST.get('session_type', 'individual')
            scheduled_start = datetime.fromisoformat(request.POST.get('scheduled_start'))
            scheduled_end = datetime.fromisoformat(request.POST.get('scheduled_end'))
            
            # Create review session
            review_session = ReviewSession.objects.create(
                section=section,
                session_type=session_type,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                objectives=request.POST.get('objectives', ''),
                moderator=request.user,
            )
            
            # Add reviewers
            reviewer_ids = request.POST.getlist('reviewers')
            for reviewer_id in reviewer_ids:
                try:
                    reviewer = section.team.members.get(id=reviewer_id)
                    ReviewParticipant.objects.create(
                        review_session=review_session,
                        reviewer=reviewer,
                        status='invited'
                    )
                except:
                    continue
            
            # Set review criteria if provided
            if request.POST.get('review_criteria'):
                criteria_list = [
                    item.strip() for item in request.POST.get('review_criteria').split('\n')
                    if item.strip()
                ]
                review_session.review_criteria = criteria_list
                review_session.save()
            
            messages.success(request, f"Review session created successfully.")
            return redirect('collaboration:review_session_detail', session_id=review_session.id)
            
        except Exception as e:
            messages.error(request, f"Error creating review session: {str(e)}")
    
    # GET request - show form
    available_reviewers = section.team.members.exclude(id=request.user.id)
    review_templates = ReviewTemplate.objects.filter(team=section.team, is_active=True)
    
    context = {
        'section': section,
        'available_reviewers': available_reviewers,
        'review_templates': review_templates,
    }
    
    return render(request, 'collaboration/create_review_session.html', context)


@login_required
def review_session_detail(request, session_id):
    """Review session detail and participation view"""
    review_session = get_object_or_404(ReviewSession, id=session_id)
    
    # Check access
    is_participant = review_session.reviewers.filter(id=request.user.id).exists()
    is_moderator = request.user == review_session.moderator
    is_team_member = review_session.section.team.members.filter(id=request.user.id).exists()
    
    if not (is_participant or is_moderator or is_team_member):
        messages.error(request, "You don't have access to this review session.")
        return redirect('opportunities:list')
    
    # Get user's participation record
    participant = None
    if is_participant:
        participant = review_session.participants.get(reviewer=request.user)
    
    # Get session comments and discussions
    comment_threads = review_session.comment_threads.filter(status='active')
    
    # Get section content and inline comments for review
    section = review_session.section
    inline_comments = section.inline_comments.filter(status='active')
    
    context = {
        'review_session': review_session,
        'section': section,
        'participant': participant,
        'is_moderator': is_moderator,
        'comment_threads': comment_threads,
        'inline_comments': inline_comments,
        'can_moderate': is_moderator,
        'can_participate': is_participant,
    }
    
    return render(request, 'collaboration/review_session_detail.html', context)


@login_required
def review_dashboard(request):
    """Dashboard showing user's review assignments and activities"""
    user = request.user
    
    # Get user's review assignments
    assigned_reviews = SectionReview.objects.filter(
        reviewer=user,
        status__in=['assigned', 'in_progress']
    ).select_related('section', 'section__team').order_by('due_date')
    
    # Get review sessions user is involved in
    review_sessions = ReviewSession.objects.filter(
        Q(reviewers=user) | Q(moderator=user),
        status__in=['scheduled', 'in_progress']
    ).distinct().select_related('section', 'section__team').order_by('scheduled_start')
    
    # Get assigned inline comments
    assigned_comments = InlineComment.objects.filter(
        assigned_to=user,
        status='active'
    ).select_related('section', 'author').order_by('-created_at')
    
    # Get user's teams and sections
    user_teams = ProposalTeam.objects.filter(members=user)
    
    # Statistics
    stats = {
        'pending_reviews': assigned_reviews.count(),
        'upcoming_sessions': review_sessions.filter(scheduled_start__gte=timezone.now()).count(),
        'assigned_comments': assigned_comments.count(),
        'overdue_reviews': assigned_reviews.filter(due_date__lt=timezone.now()).count(),
    }
    
    context = {
        'assigned_reviews': assigned_reviews[:10],  # Latest 10
        'review_sessions': review_sessions[:10],  # Latest 10
        'assigned_comments': assigned_comments[:10],  # Latest 10
        'user_teams': user_teams,
        'stats': stats,
    }
    
    return render(request, 'collaboration/review_dashboard.html', context)