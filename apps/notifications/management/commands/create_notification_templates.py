"""
Management command to create default notification templates
"""

from django.core.management.base import BaseCommand
from apps.notifications.models import NotificationTemplate


class Command(BaseCommand):
    help = 'Create default notification templates for BLACK CORAL'

    def handle(self, *args, **options):
        templates = [
            {
                'notification_type': 'opportunity_new',
                'title_template': 'New Opportunity: {opportunity_title}',
                'message_template': 'A new opportunity "{opportunity_title}" has been posted. Estimated value: ${estimated_value}. Response deadline: {response_deadline}.',
                'email_subject_template': 'BLACK CORAL: New Opportunity Available',
                'email_body_template': 'Hi {user_first_name},\n\nA new government contracting opportunity has been posted that may interest you:\n\n**{opportunity_title}**\n\nEstimated Value: ${estimated_value}\nResponse Deadline: {response_deadline}\nSolicitation Number: {solicitation_number}\n\nView the full opportunity in BLACK CORAL: {site_url}/opportunities/{opportunity_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'medium',
                'available_variables': ['opportunity_title', 'estimated_value', 'response_deadline', 'solicitation_number', 'opportunity_id'],
            },
            {
                'notification_type': 'opportunity_deadline',
                'title_template': 'Deadline Approaching: {opportunity_title}',
                'message_template': 'The deadline for "{opportunity_title}" is approaching. Only {days_remaining} days left to submit your proposal.',
                'email_subject_template': 'URGENT: Opportunity Deadline Approaching',
                'email_body_template': 'Hi {user_first_name},\n\nThis is an urgent reminder that the deadline for the following opportunity is approaching:\n\n**{opportunity_title}**\n\nDeadline: {response_deadline}\nDays Remaining: {days_remaining}\n\nMake sure your proposal is ready for submission: {site_url}/opportunities/{opportunity_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'urgent',
                'available_variables': ['opportunity_title', 'response_deadline', 'days_remaining', 'opportunity_id'],
            },
            {
                'notification_type': 'team_assignment',
                'title_template': 'Team Assignment: {team_name}',
                'message_template': 'You have been assigned to the proposal team "{team_name}" as {role}. The team is working on {opportunity_title}.',
                'email_subject_template': 'BLACK CORAL: Team Assignment',
                'email_body_template': 'Hi {user_first_name},\n\nYou have been assigned to a new proposal team:\n\n**Team:** {team_name}\n**Role:** {role}\n**Opportunity:** {opportunity_title}\n**Deadline:** {submission_deadline}\n\nJoin your team: {site_url}/teams/{team_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'high',
                'available_variables': ['team_name', 'role', 'opportunity_title', 'submission_deadline', 'team_id'],
            },
            {
                'notification_type': 'task_assigned',
                'title_template': 'Task Assigned: {task_title}',
                'message_template': 'You have been assigned a new {task_type} task: "{task_title}". Due date: {due_date}.',
                'email_subject_template': 'BLACK CORAL: New Task Assignment',
                'email_body_template': 'Hi {user_first_name},\n\nYou have been assigned a new task:\n\n**Task:** {task_title}\n**Type:** {task_type}\n**Due Date:** {due_date}\n**Team:** {team_name}\n**Priority:** {priority}\n\nView task details: {site_url}/tasks/{task_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'medium',
                'available_variables': ['task_title', 'task_type', 'due_date', 'team_name', 'priority', 'task_id'],
            },
            {
                'notification_type': 'task_due',
                'title_template': 'Task Due Soon: {task_title}',
                'message_template': 'Your task "{task_title}" is due {due_timeframe}. Please ensure it is completed on time.',
                'email_subject_template': 'BLACK CORAL: Task Due Soon',
                'email_body_template': 'Hi {user_first_name},\n\nThis is a reminder that your task is due soon:\n\n**Task:** {task_title}\n**Due Date:** {due_date}\n**Team:** {team_name}\n\nComplete your task: {site_url}/tasks/{task_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'high',
                'available_variables': ['task_title', 'due_timeframe', 'due_date', 'team_name', 'task_id'],
            },
            {
                'notification_type': 'task_overdue',
                'title_template': 'Overdue Task: {task_title}',
                'message_template': 'Your task "{task_title}" was due on {due_date} and is now overdue. Please complete it as soon as possible.',
                'email_subject_template': 'URGENT: Overdue Task',
                'email_body_template': 'Hi {user_first_name},\n\nYour task is now overdue:\n\n**Task:** {task_title}\n**Due Date:** {due_date}\n**Days Overdue:** {days_overdue}\n**Team:** {team_name}\n\nPlease complete this task immediately: {site_url}/tasks/{task_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'urgent',
                'available_variables': ['task_title', 'due_date', 'days_overdue', 'team_name', 'task_id'],
            },
            {
                'notification_type': 'milestone_approaching',
                'title_template': 'Milestone Approaching: {milestone_title}',
                'message_template': 'The milestone "{milestone_title}" is approaching. Target date: {target_date}.',
                'email_subject_template': 'BLACK CORAL: Milestone Approaching',
                'email_body_template': 'Hi {user_first_name},\n\nA milestone is approaching:\n\n**Milestone:** {milestone_title}\n**Target Date:** {target_date}\n**Team:** {team_name}\n\nView milestone details: {site_url}/teams/{team_id}/milestones/{milestone_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'medium',
                'available_variables': ['milestone_title', 'target_date', 'team_name', 'team_id', 'milestone_id'],
            },
            {
                'notification_type': 'comment_mention',
                'title_template': 'Mentioned in Comment',
                'message_template': '{author_name} mentioned you in a comment: "{comment_preview}"',
                'email_subject_template': 'BLACK CORAL: You were mentioned in a comment',
                'email_body_template': 'Hi {user_first_name},\n\n{author_name} mentioned you in a comment:\n\n**Context:** {context_title}\n**Comment:** "{comment_content}"\n\nView the full discussion: {site_url}/teams/{team_id}/comments/{comment_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'medium',
                'available_variables': ['author_name', 'comment_preview', 'comment_content', 'context_title', 'team_id', 'comment_id'],
            },
            {
                'notification_type': 'comment_reply',
                'title_template': 'Reply to Your Comment',
                'message_template': '{author_name} replied to your comment: "{reply_preview}"',
                'email_subject_template': 'BLACK CORAL: Someone replied to your comment',
                'email_body_template': 'Hi {user_first_name},\n\n{author_name} replied to your comment:\n\n**Your comment:** "{original_comment}"\n**Reply:** "{reply_content}"\n\nView the conversation: {site_url}/teams/{team_id}/comments/{comment_id}/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'medium',
                'available_variables': ['author_name', 'reply_preview', 'reply_content', 'original_comment', 'team_id', 'comment_id'],
            },
            {
                'notification_type': 'review_request',
                'title_template': 'Review Request: {item_title}',
                'message_template': 'You have been asked to review "{item_title}". Please provide your feedback.',
                'email_subject_template': 'BLACK CORAL: Review Request',
                'email_body_template': 'Hi {user_first_name},\n\nYou have been asked to review:\n\n**Item:** {item_title}\n**Type:** {item_type}\n**Requested by:** {requester_name}\n**Team:** {team_name}\n\nStart your review: {site_url}{review_url}\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'medium',
                'available_variables': ['item_title', 'item_type', 'requester_name', 'team_name', 'review_url'],
            },
            {
                'notification_type': 'decision_made',
                'title_template': 'Bid Decision: {decision_title}',
                'message_template': 'A bid decision has been made for "{opportunity_title}": {decision_result}',
                'email_subject_template': 'BLACK CORAL: Bid Decision Made',
                'email_body_template': 'Hi {user_first_name},\n\nA bid decision has been made:\n\n**Opportunity:** {opportunity_title}\n**Decision:** {decision_result}\n**Confidence Score:** {confidence_score}%\n**Rationale:** {decision_rationale}\n\nView full analysis: {site_url}/opportunities/{opportunity_id}/decision/\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'high',
                'available_variables': ['decision_title', 'opportunity_title', 'decision_result', 'confidence_score', 'decision_rationale', 'opportunity_id'],
            },
            {
                'notification_type': 'system_update',
                'title_template': 'System Update: {update_title}',
                'message_template': '{update_message}',
                'email_subject_template': 'BLACK CORAL: System Update',
                'email_body_template': 'Hi {user_first_name},\n\n{update_message}\n\nFor more information, visit: {site_url}\n\nBest regards,\nBLACK CORAL Team',
                'default_priority': 'low',
                'available_variables': ['update_title', 'update_message'],
            },
        ]

        created_count = 0
        updated_count = 0

        for template_data in templates:
            notification_type = template_data.pop('notification_type')
            
            template, created = NotificationTemplate.objects.get_or_create(
                notification_type=notification_type,
                defaults=template_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created template for: {notification_type}')
                )
            else:
                # Update existing template
                for field, value in template_data.items():
                    setattr(template, field, value)
                template.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated template for: {notification_type}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Created {created_count} new templates, updated {updated_count} existing templates.'
            )
        )