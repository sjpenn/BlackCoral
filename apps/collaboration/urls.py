"""
BLACK CORAL Collaboration URLs
URL patterns for team collaboration views
"""

from django.urls import path
from . import views
from . import workflow_views

app_name = 'collaboration'

urlpatterns = [
    # Team management
    path('', views.team_list, name='team_list'),
    path('<int:team_id>/', views.team_detail, name='team_detail'),
    
    # Task management
    path('<int:team_id>/tasks/', views.team_tasks, name='team_tasks'),
    path('<int:team_id>/tasks/create/', views.create_task, name='create_task'),
    path('<int:team_id>/tasks/<int:task_id>/status/', views.update_task_status, name='update_task_status'),
    
    # Section management
    path('<int:team_id>/sections/', views.team_sections, name='team_sections'),
    path('<int:team_id>/sections/create/', views.create_section, name='create_section'),
    path('<int:team_id>/sections/<int:section_id>/edit/', views.section_editor, name='section_editor'),
    path('<int:team_id>/sections/<int:section_id>/save/', views.save_section_content, name='save_section_content'),
    
    # AI Enhancement endpoints
    path('<int:team_id>/sections/<int:section_id>/ai/enhance/', views.ai_enhance_section, name='ai_enhance_section'),
    path('<int:team_id>/sections/<int:section_id>/ai/outline/', views.ai_generate_outline, name='ai_generate_outline'),
    path('<int:team_id>/sections/<int:section_id>/ai/compliance/', views.ai_check_compliance, name='ai_check_compliance'),
    path('<int:team_id>/sections/<int:section_id>/ai/suggestions/', views.ai_suggest_improvements, name='ai_suggest_improvements'),
    path('<int:team_id>/sections/<int:section_id>/ai/expand/', views.ai_expand_content, name='ai_expand_content'),
    
    # Communication
    path('<int:team_id>/comments/', views.team_comments, name='team_comments'),
    path('<int:team_id>/comments/create/', views.create_comment, name='create_comment'),
    
    # Milestones
    path('<int:team_id>/milestones/', views.team_milestones, name='team_milestones'),
    
    # Analytics
    path('<int:team_id>/analytics/', views.team_analytics, name='team_analytics'),
    
    # Workflow and Approval Management
    path('<int:team_id>/sections/<int:section_id>/workflow/', workflow_views.section_workflow, name='section_workflow'),
    path('<int:team_id>/sections/<int:section_id>/workflow/start/', workflow_views.start_section_workflow, name='start_section_workflow'),
    path('<int:team_id>/sections/<int:section_id>/workflow/advance/', workflow_views.advance_workflow, name='advance_workflow'),
    path('<int:team_id>/sections/<int:section_id>/review/<int:review_id>/', workflow_views.review_section, name='review_section'),
    path('<int:team_id>/sections/<int:section_id>/approve/<int:approval_id>/', workflow_views.approve_section, name='approve_section'),
    
    # User Dashboards
    path('reviews/', workflow_views.review_dashboard, name='review_dashboard'),
    path('approvals/', workflow_views.approval_dashboard, name='approval_dashboard'),
    
    # Workflow Templates
    path('<int:team_id>/workflow-templates/', workflow_views.workflow_templates, name='workflow_templates'),
    path('<int:team_id>/workflow-templates/create/', workflow_views.create_workflow_template, name='create_workflow_template'),
    
    # HTMX endpoints
    path('<int:team_id>/htmx/dashboard/', views.team_dashboard_htmx, name='dashboard_htmx'),
    path('<int:team_id>/tasks/<int:task_id>/htmx/actions/', views.task_quick_actions_htmx, name='task_actions_htmx'),
    
    # Document Assembly Integration
    path('<int:team_id>/documents/', views.team_documents, name='team_documents'),
]