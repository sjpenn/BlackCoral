"""
BLACK CORAL Notification Signals
Automatic notification triggers for collaboration events
"""

import logging
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.collaboration.models import (
    ProposalTeam, TeamMembership, ProposalSection, TaskItem, 
    TeamComment, ProposalMilestone, TimeLog
)
from apps.opportunities.models import Opportunity
from .services import notification_service

User = get_user_model()
logger = logging.getLogger(__name__)


# Team Formation and Management Signals

@receiver(post_save, sender=ProposalTeam)
def team_created_notification(sender, instance, created, **kwargs):
    """Notify when a new proposal team is created"""
    if created:
        # Notify team lead
        if instance.lead:
            notification_service.create_notification(
                user=instance.lead,
                notification_type='team_assignment',
                title=f"You've been assigned as lead for {instance.name}",
                message=f"You are now the team lead for the {instance.opportunity.solicitation_number} proposal team.",
                content_object=instance,
                action_url=f"/teams/{instance.id}/",
                action_label="View Team",
                priority='high'
            )


@receiver(post_save, sender=TeamMembership)
def team_membership_notification(sender, instance, created, **kwargs):
    """Notify when users are added to teams"""
    if created and instance.is_active:
        # Notify new team member
        notification_service.create_notification(
            user=instance.user,
            notification_type='team_assignment',
            title=f"Added to {instance.team.name}",
            message=f"You've been assigned as {instance.get_role_display()} on the {instance.team.opportunity.solicitation_number} proposal team.",
            content_object=instance.team,
            action_url=f"/teams/{instance.team.id}/",
            action_label="View Team",
            priority='high'
        )
        
        # Notify team lead about new member
        if instance.team.lead and instance.team.lead != instance.user:
            notification_service.create_notification(
                user=instance.team.lead,
                notification_type='team_assignment',
                title=f"New team member: {instance.user.get_full_name()}",
                message=f"{instance.user.get_full_name()} has joined as {instance.get_role_display()}",
                content_object=instance.team,
                action_url=f"/teams/{instance.team.id}/members/",
                action_label="View Members",
                priority='medium'
            )


# Task Management Signals

@receiver(post_save, sender=TaskItem)
def task_assignment_notification(sender, instance, created, **kwargs):
    """Notify when tasks are created or assigned"""
    if created and instance.assigned_to:
        # Notify assigned user
        notification_service.create_notification(
            user=instance.assigned_to,
            notification_type='task_assigned',
            title=f"New task assigned: {instance.title}",
            message=f"You've been assigned a new {instance.get_task_type_display().lower()} task for {instance.team.name}.",
            content_object=instance,
            action_url=f"/tasks/{instance.id}/",
            action_label="View Task",
            priority='high' if instance.priority in ['high', 'critical'] else 'medium'
        )
        
        # Notify task creator if different from assignee
        if instance.created_by and instance.created_by != instance.assigned_to:
            notification_service.create_notification(
                user=instance.created_by,
                notification_type='task_assigned',
                title=f"Task assigned to {instance.assigned_to.get_full_name()}",
                message=f"Your task '{instance.title}' has been assigned to {instance.assigned_to.get_full_name()}.",
                content_object=instance,
                action_url=f"/tasks/{instance.id}/",
                action_label="View Task",
                priority='low'
            )


@receiver(pre_save, sender=TaskItem)
def task_status_change_notification(sender, instance, **kwargs):
    """Notify when task status changes"""
    if instance.pk:  # Only for existing tasks
        try:
            old_task = TaskItem.objects.get(pk=instance.pk)
            
            # Task completed
            if old_task.status != 'completed' and instance.status == 'completed':
                # Notify team lead
                if instance.team.lead and instance.team.lead != instance.assigned_to:
                    notification_service.create_notification(
                        user=instance.team.lead,
                        notification_type='task_assigned',
                        title=f"Task completed: {instance.title}",
                        message=f"{instance.assigned_to.get_full_name()} completed the task '{instance.title}'.",
                        content_object=instance,
                        action_url=f"/tasks/{instance.id}/",
                        action_label="View Task",
                        priority='low'
                    )
                
                # Update section progress if task belongs to a section
                if instance.section:
                    section_tasks = instance.section.tasks.all()
                    completed_tasks = section_tasks.filter(status='completed').count()
                    total_tasks = section_tasks.count()
                    
                    if total_tasks > 0:
                        progress = (completed_tasks / total_tasks) * 100
                        
                        # Notify section owner if significant progress made
                        if progress >= 100 and instance.section.assigned_to:
                            notification_service.create_notification(
                                user=instance.section.assigned_to,
                                notification_type='milestone_approaching',
                                title=f"Section tasks completed: {instance.section.title}",
                                message=f"All tasks for section '{instance.section.title}' have been completed.",
                                content_object=instance.section,
                                action_url=f"/sections/{instance.section.id}/",
                                action_label="View Section",
                                priority='medium'
                            )
            
            # Assignment change
            if old_task.assigned_to != instance.assigned_to and instance.assigned_to:
                notification_service.create_notification(
                    user=instance.assigned_to,
                    notification_type='task_assigned',
                    title=f"Task reassigned: {instance.title}",
                    message=f"You've been assigned the task '{instance.title}' previously assigned to {old_task.assigned_to.get_full_name() if old_task.assigned_to else 'no one'}.",
                    content_object=instance,
                    action_url=f"/tasks/{instance.id}/",
                    action_label="View Task",
                    priority='high'
                )
                
        except TaskItem.DoesNotExist:
            pass


# Section Management Signals

@receiver(post_save, sender=ProposalSection)
def section_assignment_notification(sender, instance, created, **kwargs):
    """Notify when sections are assigned"""
    if created and instance.assigned_to:
        notification_service.create_notification(
            user=instance.assigned_to,
            notification_type='task_assigned',
            title=f"Section assigned: {instance.title}",
            message=f"You've been assigned to write section {instance.section_number}: {instance.title}",
            content_object=instance,
            action_url=f"/sections/{instance.id}/",
            action_label="View Section",
            priority='high'
        )


@receiver(m2m_changed, sender=ProposalSection.reviewers.through)
def section_reviewer_notification(sender, instance, action, pk_set, **kwargs):
    """Notify when reviewers are added to sections"""
    if action == 'post_add' and pk_set:
        reviewers = User.objects.filter(pk__in=pk_set)
        for reviewer in reviewers:
            notification_service.create_notification(
                user=reviewer,
                notification_type='review_request',
                title=f"Review requested: {instance.title}",
                message=f"You've been asked to review section {instance.section_number}: {instance.title}",
                content_object=instance,
                action_url=f"/sections/{instance.id}/review/",
                action_label="Review Section",
                priority='medium'
            )


# Comment and Communication Signals

@receiver(post_save, sender=TeamComment)
def comment_notification(sender, instance, created, **kwargs):
    """Notify when comments are posted"""
    if created:
        # Notify mentioned users
        for mentioned_user in instance.mentioned_users.all():
            if mentioned_user != instance.author:
                notification_service.create_notification(
                    user=mentioned_user,
                    notification_type='comment_mention',
                    title=f"Mentioned in comment by {instance.author.get_full_name()}",
                    message=f"You were mentioned in a comment: {instance.content[:100]}...",
                    content_object=instance,
                    action_url=f"/teams/{instance.team.id}/comments/{instance.id}/",
                    action_label="View Comment",
                    priority='medium'
                )
        
        # Notify parent comment author for replies
        if instance.parent_comment and instance.parent_comment.author != instance.author:
            notification_service.create_notification(
                user=instance.parent_comment.author,
                notification_type='comment_reply',
                title=f"Reply to your comment",
                message=f"{instance.author.get_full_name()} replied to your comment: {instance.content[:100]}...",
                content_object=instance,
                action_url=f"/teams/{instance.team.id}/comments/{instance.id}/",
                action_label="View Reply",
                priority='medium'
            )
        
        # Notify task/section assignees for context-specific comments
        if instance.task and instance.task.assigned_to and instance.task.assigned_to != instance.author:
            notification_service.create_notification(
                user=instance.task.assigned_to,
                notification_type='comment_mention',
                title=f"Comment on your task: {instance.task.title}",
                message=f"{instance.author.get_full_name()} commented on your task: {instance.content[:100]}...",
                content_object=instance.task,
                action_url=f"/tasks/{instance.task.id}/comments/",
                action_label="View Comments",
                priority='medium'
            )
        
        if instance.section and instance.section.assigned_to and instance.section.assigned_to != instance.author:
            notification_service.create_notification(
                user=instance.section.assigned_to,
                notification_type='comment_mention',
                title=f"Comment on your section: {instance.section.title}",
                message=f"{instance.author.get_full_name()} commented on your section: {instance.content[:100]}...",
                content_object=instance.section,
                action_url=f"/sections/{instance.section.id}/comments/",
                action_label="View Comments",
                priority='medium'
            )


# Milestone and Deadline Signals

@receiver(post_save, sender=ProposalMilestone)
def milestone_notification(sender, instance, created, **kwargs):
    """Notify when milestones are created or approaching"""
    if created and instance.responsible_person:
        notification_service.create_notification(
            user=instance.responsible_person,
            notification_type='milestone_approaching',
            title=f"New milestone assigned: {instance.title}",
            message=f"You're responsible for the milestone '{instance.title}' due on {instance.target_date.strftime('%B %d, %Y')}",
            content_object=instance,
            action_url=f"/teams/{instance.team.id}/milestones/{instance.id}/",
            action_label="View Milestone",
            priority='high'
        )


# Time Tracking Signals

@receiver(post_save, sender=TimeLog)
def time_log_notification(sender, instance, created, **kwargs):
    """Notify when time logs need approval"""
    if created and instance.team.lead and instance.team.lead != instance.user:
        notification_service.create_notification(
            user=instance.team.lead,
            notification_type='review_request',
            title=f"Time log approval needed",
            message=f"{instance.user.get_full_name()} logged {instance.hours} hours for review",
            content_object=instance,
            action_url=f"/teams/{instance.team.id}/time-logs/",
            action_label="Review Time Logs",
            priority='low'
        )


# Opportunity and Deadline Signals

@receiver(post_save, sender=Opportunity)
def opportunity_deadline_notification(sender, instance, created, **kwargs):
    """Notify teams about upcoming opportunity deadlines"""
    if not created and instance.response_date:
        # Check if deadline is approaching (within 7 days)
        days_until_deadline = (instance.response_date.date() - timezone.now().date()).days
        
        if days_until_deadline <= 7 and days_until_deadline > 0:
            try:
                team = instance.proposal_team
                notification_service.notify_team_members(
                    team=team,
                    notification_type='opportunity_deadline',
                    title=f"Deadline approaching: {instance.solicitation_number}",
                    message=f"Only {days_until_deadline} days left to submit proposal for {instance.solicitation_number}",
                    content_object=instance,
                    action_url=f"/opportunities/{instance.id}/",
                    action_label="View Opportunity",
                    priority='urgent' if days_until_deadline <= 3 else 'high'
                )
            except ProposalTeam.DoesNotExist:
                pass


# Daily/Periodic Notification Checks (to be called by Celery tasks)

def check_overdue_tasks():
    """Check for overdue tasks and send notifications"""
    overdue_tasks = TaskItem.objects.filter(
        due_date__lt=timezone.now(),
        status__in=['todo', 'in_progress'],
        assigned_to__isnull=False
    )
    
    for task in overdue_tasks:
        # Check if we already sent an overdue notification today
        today = timezone.now().date()
        existing_notification = task.assigned_to.notifications.filter(
            notification_type='task_overdue',
            content_type__model='taskitem',
            object_id=task.id,
            created_at__date=today
        ).exists()
        
        if not existing_notification:
            notification_service.create_notification(
                user=task.assigned_to,
                notification_type='task_overdue',
                title=f"Overdue task: {task.title}",
                message=f"Your task '{task.title}' was due on {task.due_date.strftime('%B %d, %Y')}",
                content_object=task,
                action_url=f"/tasks/{task.id}/",
                action_label="View Task",
                priority='urgent'
            )


def check_approaching_deadlines():
    """Check for approaching task and milestone deadlines"""
    tomorrow = timezone.now() + timedelta(days=1)
    next_week = timezone.now() + timedelta(days=7)
    
    # Tasks due tomorrow
    tasks_due_tomorrow = TaskItem.objects.filter(
        due_date__date=tomorrow.date(),
        status__in=['todo', 'in_progress'],
        assigned_to__isnull=False
    )
    
    for task in tasks_due_tomorrow:
        notification_service.create_notification(
            user=task.assigned_to,
            notification_type='task_due',
            title=f"Task due tomorrow: {task.title}",
            message=f"Your task '{task.title}' is due tomorrow ({task.due_date.strftime('%B %d, %Y')})",
            content_object=task,
            action_url=f"/tasks/{task.id}/",
            action_label="View Task",
            priority='high'
        )
    
    # Milestones due within a week
    milestones_due_soon = ProposalMilestone.objects.filter(
        target_date__lte=next_week,
        target_date__gte=timezone.now(),
        is_completed=False,
        responsible_person__isnull=False
    )
    
    for milestone in milestones_due_soon:
        days_left = (milestone.target_date.date() - timezone.now().date()).days
        notification_service.create_notification(
            user=milestone.responsible_person,
            notification_type='milestone_approaching',
            title=f"Milestone due in {days_left} days: {milestone.title}",
            message=f"Milestone '{milestone.title}' is due on {milestone.target_date.strftime('%B %d, %Y')}",
            content_object=milestone,
            action_url=f"/teams/{milestone.team.id}/milestones/{milestone.id}/",
            action_label="View Milestone",
            priority='high' if days_left <= 3 else 'medium'
        )


def check_inactive_teams():
    """Check for teams with no recent activity"""
    week_ago = timezone.now() - timedelta(days=7)
    
    inactive_teams = ProposalTeam.objects.filter(
        status='active',
        updated_at__lt=week_ago
    ).exclude(
        # Exclude teams with recent task updates
        tasks__updated_at__gte=week_ago
    ).exclude(
        # Exclude teams with recent comments
        comments__created_at__gte=week_ago
    )
    
    for team in inactive_teams:
        if team.lead:
            notification_service.create_notification(
                user=team.lead,
                notification_type='system_update',
                title=f"Team inactivity alert: {team.name}",
                message=f"No activity detected for team {team.name} in the past week",
                content_object=team,
                action_url=f"/teams/{team.id}/",
                action_label="View Team",
                priority='medium'
            )


logger.info("BLACK CORAL notification signals registered")