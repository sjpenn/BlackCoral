#!/usr/bin/env python
"""
Create test data for collaboration system
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.append('/Users/sjpenn/Sites/BlackCoral')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.opportunities.models import Opportunity
from apps.collaboration.models import ProposalTeam, TeamMembership, ProposalSection
from apps.collaboration.workflow_services import workflow_service
from django.utils import timezone

User = get_user_model()

def create_test_data():
    print("Creating collaboration test data...")
    
    # Create test user if doesn't exist
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'proposal_manager'
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()
        print(f"Created test user: {user.username}")
    
    # Create test opportunity if doesn't exist
    opportunity, created = Opportunity.objects.get_or_create(
        solicitation_number='TEST-2024-001',
        defaults={
            'title': 'Test Opportunity for Collaboration',
            'description': 'Test opportunity for testing collaboration features',
            'posted_date': timezone.now(),
            'response_date': timezone.now() + timedelta(days=30),
            'source_url': 'https://test.example.com',
            'set_aside_type': 'unrestricted',
            'place_of_performance': {'city': 'Remote', 'state': 'N/A'}
        }
    )
    if created:
        print(f"Created test opportunity: {opportunity.solicitation_number}")
    
    # Create test team if doesn't exist
    team, created = ProposalTeam.objects.get_or_create(
        opportunity=opportunity,
        defaults={
            'name': 'Test Proposal Team',
            'description': 'Team for testing collaboration features',
            'status': 'active',
            'lead': user,
            'submission_deadline': timezone.now() + timedelta(days=25)
        }
    )
    if created:
        print(f"Created test team: {team.name}")
    
    # Add user as team member
    membership, created = TeamMembership.objects.get_or_create(
        team=team,
        user=user,
        defaults={
            'role': 'lead',
            'is_active': True,
            'hours_committed': 40.0
        }
    )
    if created:
        print(f"Added {user.username} to team as {membership.role}")
    
    # Create test proposal sections
    sections_data = [
        {
            'section_number': '1.0',
            'title': 'Executive Summary',
            'description': 'High-level overview of the proposal',
            'word_count_target': 500,
            'priority': 'high'
        },
        {
            'section_number': '2.0',
            'title': 'Technical Approach',
            'description': 'Detailed technical methodology and approach',
            'word_count_target': 2000,
            'priority': 'critical'
        },
        {
            'section_number': '3.0',
            'title': 'Management Plan',
            'description': 'Project management and organizational structure',
            'word_count_target': 1500,
            'priority': 'high'
        },
        {
            'section_number': '4.0',
            'title': 'Past Performance',
            'description': 'Relevant experience and case studies',
            'word_count_target': 1000,
            'priority': 'medium'
        }
    ]
    
    for section_data in sections_data:
        section, created = ProposalSection.objects.get_or_create(
            team=team,
            section_number=section_data['section_number'],
            defaults={
                'title': section_data['title'],
                'description': section_data['description'],
                'word_count_target': section_data['word_count_target'],
                'priority': section_data['priority'],
                'assigned_to': user,
                'due_date': timezone.now() + timedelta(days=20),
                'content': f'<p>This is sample content for {section_data["title"]}. You can edit this using the rich text editor.</p>'
            }
        )
        if created:
            print(f"Created section: {section.section_number} - {section.title}")
    
    # Create workflow templates and start workflows
    print("\nSetting up workflows...")
    
    # Create default workflow templates
    templates = workflow_service.create_default_templates(team)
    print(f"Created {len(templates)} workflow templates")
    
    # Start workflows for all sections
    for section_data in sections_data:
        section = ProposalSection.objects.get(
            team=team, 
            section_number=section_data['section_number']
        )
        
        # Start workflow for this section
        workflow = workflow_service.start_workflow(section)
        print(f"Started workflow for {section.title} - Status: {workflow.status}")
    
    print("\nTest data creation complete!")
    print(f"Team ID: {team.id}")
    print(f"Access team at: http://localhost:8000/teams/{team.id}/")
    print(f"Access sections at: http://localhost:8000/teams/{team.id}/sections/")
    print(f"Access workflows at: http://localhost:8000/teams/{team.id}/sections/[section_id]/workflow/")

if __name__ == '__main__':
    create_test_data()