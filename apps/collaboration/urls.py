"""
BLACK CORAL Collaboration URLs
URL patterns for team collaboration views
"""

from django.urls import path
from . import views

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
    
    # Communication
    path('<int:team_id>/comments/', views.team_comments, name='team_comments'),
    path('<int:team_id>/comments/create/', views.create_comment, name='create_comment'),
    
    # Milestones
    path('<int:team_id>/milestones/', views.team_milestones, name='team_milestones'),
    
    # Analytics
    path('<int:team_id>/analytics/', views.team_analytics, name='team_analytics'),
    
    # HTMX endpoints
    path('<int:team_id>/htmx/dashboard/', views.team_dashboard_htmx, name='dashboard_htmx'),
    path('<int:team_id>/tasks/<int:task_id>/htmx/actions/', views.task_quick_actions_htmx, name='task_actions_htmx'),
]