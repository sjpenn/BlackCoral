"""
Section Workflow and Approval Services
Business logic for managing proposal section workflows, reviews, and approvals
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import (
    ProposalSection, SectionReview, SectionApproval, 
    WorkflowTemplate, SectionWorkflowInstance, TeamMembership
)
from apps.notifications.services import notification_service

User = get_user_model()
logger = logging.getLogger(__name__)


class WorkflowService:
    """
    Manages section workflow orchestration
    """
    
    def create_default_templates(self, team):
        """Create default workflow templates for a team"""
        templates = [
            {
                'name': 'Standard Technical Section',
                'description': 'Standard workflow for technical sections',
                'section_types': ['technical_approach', 'methodology', 'architecture'],
                'required_reviews': ['technical', 'compliance'],
                'approval_sequence': ['technical_lead', 'proposal_manager', 'team_lead'],
                'is_default': True
            },
            {
                'name': 'Management Section',
                'description': 'Workflow for management and organizational sections',
                'section_types': ['management_plan', 'staffing', 'organization'],
                'required_reviews': ['editorial', 'compliance'],
                'approval_sequence': ['proposal_manager', 'team_lead'],
                'is_default': False
            },
            {
                'name': 'Executive Summary',
                'description': 'High-priority workflow for executive summary',
                'section_types': ['executive_summary'],
                'required_reviews': ['technical', 'editorial', 'compliance'],
                'approval_sequence': ['technical_lead', 'proposal_manager', 'team_lead', 'final_authority'],
                'is_default': False
            },
            {
                'name': 'Past Performance',
                'description': 'Workflow for past performance sections',
                'section_types': ['past_performance', 'experience'],
                'required_reviews': ['compliance', 'quality'],
                'approval_sequence': ['proposal_manager', 'team_lead'],
                'is_default': False
            }
        ]
        
        created_templates = []
        for template_data in templates:
            template, created = WorkflowTemplate.objects.get_or_create(
                team=team,
                name=template_data['name'],
                defaults={
                    'description': template_data['description'],
                    'section_types': template_data['section_types'],
                    'required_reviews': template_data['required_reviews'],
                    'approval_sequence': template_data['approval_sequence'],
                    'is_default': template_data['is_default']
                }
            )
            if created:
                created_templates.append(template)
        
        return created_templates
    
    def start_workflow(self, section: ProposalSection) -> SectionWorkflowInstance:
        """Initialize workflow for a section"""
        
        # Get or create workflow instance
        workflow, created = SectionWorkflowInstance.objects.get_or_create(
            section=section,
            defaults={
                'status': 'not_started',
                'started_at': timezone.now()
            }
        )
        
        if created:
            # Determine appropriate template
            template = self._get_workflow_template(section)
            workflow.template = template
            
            if template:
                # Set up workflow steps
                steps = []
                if template.required_reviews:
                    steps.append('review')
                if template.approval_sequence:
                    steps.append('approval')
                
                workflow.steps_pending = steps
                if steps:
                    workflow.current_step = steps[0]
                    workflow.status = 'in_review' if steps[0] == 'review' else 'in_approval'
            
            workflow.save()
            
            # Start the first step
            if workflow.current_step == 'review':
                self._create_reviews(section, template)
            elif workflow.current_step == 'approval':
                self._create_approvals(section, template)
        
        return workflow
    
    def advance_workflow(self, section: ProposalSection) -> bool:
        """Advance section to next workflow step"""
        try:
            workflow = section.workflow
        except SectionWorkflowInstance.DoesNotExist:
            workflow = self.start_workflow(section)
        
        # Check if current step is complete
        if not self._is_step_complete(workflow):
            return False
        
        # Advance to next step
        success = workflow.advance_workflow()
        
        if success and workflow.current_step:
            # Start the new step
            if workflow.current_step == 'review':
                self._create_reviews(section, workflow.template)
                workflow.status = 'in_review'
            elif workflow.current_step == 'approval':
                self._create_approvals(section, workflow.template)
                workflow.status = 'in_approval'
            
            workflow.save()
        
        return success
    
    def _get_workflow_template(self, section: ProposalSection) -> Optional[WorkflowTemplate]:
        """Get appropriate workflow template for section"""
        team = section.team
        
        # First try to find template by section type/title
        templates = WorkflowTemplate.objects.filter(team=team, is_active=True)
        
        # Check if section type matches any template
        section_key = section.title.lower().replace(' ', '_')
        for template in templates:
            if any(section_type in section_key for section_type in template.section_types):
                return template
        
        # Fall back to default template
        default_template = templates.filter(is_default=True).first()
        return default_template
    
    def _create_reviews(self, section: ProposalSection, template: Optional[WorkflowTemplate]):
        """Create required reviews for section"""
        if not template or not template.required_reviews:
            return
        
        team = section.team
        review_duration = timedelta(days=template.default_review_duration)
        
        for review_type in template.required_reviews:
            # Find appropriate reviewer
            reviewer = self._get_reviewer(team, review_type)
            if reviewer:
                SectionReview.objects.create(
                    section=section,
                    reviewer=reviewer,
                    review_type=review_type,
                    due_date=timezone.now() + review_duration,
                    instructions=f"Please review this {section.title} section for {review_type} compliance and quality."
                )
                
                # Send notification
                notification_service.create_notification(
                    user=reviewer,
                    notification_type='review_assigned',
                    title=f"Section Review Assigned: {section.title}",
                    message=f"You've been assigned a {review_type} review for {section.title}",
                    content_object=section,
                    action_url=f"/teams/{team.id}/sections/{section.id}/review/",
                    action_label="Start Review",
                    priority='high'
                )
    
    def _create_approvals(self, section: ProposalSection, template: Optional[WorkflowTemplate]):
        """Create required approvals for section"""
        if not template or not template.approval_sequence:
            return
        
        team = section.team
        approval_duration = timedelta(days=template.default_approval_duration)
        section_version = self._get_section_version(section)
        
        for approval_level in template.approval_sequence:
            # Find appropriate approver
            approver = self._get_approver(team, approval_level)
            if approver:
                SectionApproval.objects.create(
                    section=section,
                    approver=approver,
                    approval_level=approval_level,
                    due_date=timezone.now() + approval_duration,
                    section_version=section_version,
                    priority='high' if approval_level == 'final_authority' else 'medium'
                )
                
                # Send notification
                notification_service.create_notification(
                    user=approver,
                    notification_type='approval_requested',
                    title=f"Approval Required: {section.title}",
                    message=f"Your {approval_level.replace('_', ' ').title()} approval is needed for {section.title}",
                    content_object=section,
                    action_url=f"/teams/{team.id}/sections/{section.id}/approve/",
                    action_label="Review & Approve",
                    priority='high' if approval_level == 'final_authority' else 'medium'
                )
    
    def _get_reviewer(self, team, review_type: str) -> Optional[User]:
        """Find appropriate reviewer based on review type"""
        role_mapping = {
            'technical': ['technical_lead', 'sme'],
            'compliance': ['compliance', 'proposal_manager'],
            'editorial': ['editor', 'writer'],
            'final': ['proposal_manager', 'team_lead'],
            'quality': ['proposal_manager', 'lead']
        }
        
        roles = role_mapping.get(review_type, ['proposal_manager'])
        
        for role in roles:
            member = TeamMembership.objects.filter(
                team=team, 
                role=role, 
                is_active=True
            ).first()
            if member:
                return member.user
        
        # Fallback to team lead
        return team.lead
    
    def _get_approver(self, team, approval_level: str) -> Optional[User]:
        """Find appropriate approver based on approval level"""
        if approval_level == 'team_lead':
            return team.lead
        elif approval_level == 'proposal_manager':
            return team.proposal_manager
        elif approval_level == 'technical_lead':
            member = TeamMembership.objects.filter(
                team=team, 
                role='technical_lead', 
                is_active=True
            ).first()
            return member.user if member else team.lead
        elif approval_level == 'final_authority':
            return team.lead  # Team lead has final authority
        else:
            # Look for specific role
            member = TeamMembership.objects.filter(
                team=team, 
                role=approval_level, 
                is_active=True
            ).first()
            return member.user if member else team.lead
    
    def _is_step_complete(self, workflow: SectionWorkflowInstance) -> bool:
        """Check if current workflow step is complete"""
        if workflow.current_step == 'review':
            # All reviews must be completed
            pending_reviews = workflow.section.reviews.filter(
                status__in=['assigned', 'in_progress']
            )
            return not pending_reviews.exists()
        
        elif workflow.current_step == 'approval':
            # All approvals must be completed (approved or rejected)
            pending_approvals = workflow.section.approvals.filter(status='pending')
            return not pending_approvals.exists()
        
        return True
    
    def _get_section_version(self, section: ProposalSection) -> str:
        """Generate version hash for section content"""
        content = section.content or ""
        return hashlib.md5(content.encode()).hexdigest()


class ReviewService:
    """
    Manages section review processes
    """
    
    def start_review(self, review: SectionReview):
        """Start a section review"""
        review.status = 'in_progress'
        review.started_at = timezone.now()
        review.save()
        
        logger.info(f"Review started: {review}")
    
    def complete_review(self, review: SectionReview, feedback: str, 
                       recommendation: str, scores: Dict[str, int] = None):
        """Complete a section review"""
        review.status = 'completed'
        review.completed_at = timezone.now()
        review.feedback = feedback
        review.recommendation = recommendation
        
        # Set scores if provided
        if scores:
            review.technical_accuracy = scores.get('technical_accuracy')
            review.clarity_score = scores.get('clarity_score')
            review.compliance_score = scores.get('compliance_score')
            review.overall_quality = scores.get('overall_quality')
        
        review.save()
        
        # Notify section author
        if review.section.assigned_to:
            notification_service.create_notification(
                user=review.section.assigned_to,
                notification_type='review_completed',
                title=f"Review Completed: {review.section.title}",
                message=f"{review.get_review_type_display()} review completed with recommendation: {review.get_recommendation_display()}",
                content_object=review.section,
                action_url=f"/teams/{review.section.team.id}/sections/{review.section.id}/",
                action_label="View Feedback"
            )
        
        # Check if all reviews are complete and advance workflow
        workflow_service = WorkflowService()
        workflow_service.advance_workflow(review.section)
        
        logger.info(f"Review completed: {review}")
    
    def get_review_dashboard(self, user: User) -> Dict:
        """Get review dashboard data for user"""
        pending_reviews = SectionReview.objects.filter(
            reviewer=user,
            status__in=['assigned', 'in_progress']
        ).select_related('section', 'section__team').order_by('due_date')
        
        overdue_reviews = [r for r in pending_reviews if r.is_overdue]
        
        completed_reviews = SectionReview.objects.filter(
            reviewer=user,
            status='completed'
        ).select_related('section').order_by('-completed_at')[:10]
        
        return {
            'pending_reviews': pending_reviews,
            'overdue_reviews': overdue_reviews,
            'completed_reviews': completed_reviews,
            'total_pending': pending_reviews.count(),
            'total_overdue': len(overdue_reviews)
        }


class ApprovalService:
    """
    Manages section approval processes
    """
    
    def approve_section(self, approval: SectionApproval, comments: str = "", conditions: str = ""):
        """Approve a section"""
        approval.approve(comments, conditions)
        
        # Notify requester
        if approval.requested_by:
            status_text = "conditionally approved" if conditions else "approved"
            notification_service.create_notification(
                user=approval.requested_by,
                notification_type='approval_completed',
                title=f"Section {status_text.title()}: {approval.section.title}",
                message=f"Your section has been {status_text} by {approval.approver.get_full_name()}",
                content_object=approval.section,
                action_url=f"/teams/{approval.section.team.id}/sections/{approval.section.id}/",
                action_label="View Section"
            )
        
        # Check if all approvals are complete and advance workflow
        workflow_service = WorkflowService()
        workflow_service.advance_workflow(approval.section)
        
        logger.info(f"Section approved: {approval}")
    
    def reject_section(self, approval: SectionApproval, comments: str):
        """Reject a section"""
        approval.reject(comments)
        
        # Notify author and requester
        recipients = [approval.section.assigned_to, approval.requested_by]
        for recipient in set(filter(None, recipients)):
            notification_service.create_notification(
                user=recipient,
                notification_type='approval_rejected',
                title=f"Section Rejected: {approval.section.title}",
                message=f"Section rejected by {approval.approver.get_full_name()}. Revision needed.",
                content_object=approval.section,
                action_url=f"/teams/{approval.section.team.id}/sections/{approval.section.id}/edit/",
                action_label="Revise Section",
                priority='high'
            )
        
        logger.info(f"Section rejected: {approval}")
    
    def get_approval_dashboard(self, user: User) -> Dict:
        """Get approval dashboard data for user"""
        pending_approvals = SectionApproval.objects.filter(
            approver=user,
            status='pending'
        ).select_related('section', 'section__team').order_by('due_date')
        
        overdue_approvals = [a for a in pending_approvals if a.is_overdue]
        
        completed_approvals = SectionApproval.objects.filter(
            approver=user,
            status__in=['approved', 'rejected', 'conditional']
        ).select_related('section').order_by('-responded_at')[:10]
        
        return {
            'pending_approvals': pending_approvals,
            'overdue_approvals': overdue_approvals,
            'completed_approvals': completed_approvals,
            'total_pending': pending_approvals.count(),
            'total_overdue': len(overdue_approvals)
        }


# Global service instances
workflow_service = WorkflowService()
review_service = ReviewService()
approval_service = ApprovalService()