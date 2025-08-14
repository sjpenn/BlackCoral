"""
BLACK CORAL Documents URLs
URL patterns for document assembly and export views
"""

from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # Legacy documents list
    path('', views.document_list, name='document_list'),
    
    # Document Assembly URLs
    path('teams/<int:team_id>/assembly/', views.assembly_list, name='assembly_list'),
    path('teams/<int:team_id>/assembly/create/', views.create_assembly, name='create_assembly'),
    path('teams/<int:team_id>/assembly/<int:config_id>/', views.assembly_detail, name='assembly_detail'),
    path('teams/<int:team_id>/assembly/<int:config_id>/preview/', views.preview_document, name='preview_document'),
    
    # Export functionality
    path('teams/<int:team_id>/assembly/<int:config_id>/export/', views.export_document, name='export_document'),
    path('teams/<int:team_id>/jobs/<int:job_id>/download/', views.download_export, name='download_export'),
    path('teams/<int:team_id>/jobs/<int:job_id>/status/', views.export_status, name='export_status'),
    
    # Variable management
    path('teams/<int:team_id>/assembly/<int:config_id>/variables/update/', views.update_variable, name='update_variable'),
    
    # Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/<int:template_id>/', views.template_detail, name='template_detail'),
    
    # User's jobs
    path('jobs/', views.jobs_list, name='jobs_list'),
]