"""
URL patterns for BLACK CORAL Documents app
Including chat endpoints for AI-powered document interaction
"""

from django.urls import path, include
from . import views_minimal as views
# from . import api_views  # Import API views for PDF extraction (temporarily disabled)
# from . import chat_views  # Temporarily disabled due to missing dependencies

app_name = 'documents'

urlpatterns = [
    # Document management
    path('', views.document_list, name='list'),
    path('upload/', views.document_upload, name='upload'),
    path('<int:document_id>/', views.document_detail, name='detail'),
    path('<int:document_id>/download/', views.document_download, name='download'),
    path('<int:document_id>/delete/', views.document_delete, name='delete'),
    path('<int:document_id>/process/', views.process_document, name='process'),
    path('<int:document_id>/analysis/', views.document_analysis, name='analysis'),
    
    # Document sharing
    path('<uuid:document_id>/share/', views.share_document, name='share'),
    path('share/<str:token>/', views.shared_document_view, name='shared_view'),
    
    # Document templates and assembly
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<uuid:template_id>/', views.template_detail, name='template_detail'),
    path('templates/<uuid:template_id>/edit/', views.template_edit, name='template_edit'),
    path('assembly/', views.assembly_list, name='assembly_list'),
    path('assembly/create/', views.assembly_create, name='assembly_create'),
    path('assembly/<uuid:config_id>/', views.assembly_detail, name='assembly_detail'),
    path('assembly/<uuid:config_id>/generate/', views.generate_document, name='generate_document'),
    path('assembly/<uuid:config_id>/export/', views.export_document, name='export_document'),
    
    # Export jobs
    path('exports/', views.export_list, name='export_list'),
    path('exports/<uuid:job_id>/', views.export_detail, name='export_detail'),
    path('exports/<uuid:job_id>/download/', views.export_download, name='export_download'),
    
    # AI-Powered Document Chat URLs - Temporarily disabled
    # path('chat/', chat_views.chat_home, name='chat_home'),
    # path('chat/create/', chat_views.create_chat_session, name='create_chat_session'),
    # path('chat/session/<uuid:session_id>/', chat_views.chat_session, name='chat_session'),
    # path('chat/session/<uuid:session_id>/messages/', chat_views.get_session_messages, name='get_session_messages'),
    # path('chat/session/<uuid:session_id>/settings/', chat_views.update_session_settings, name='update_session_settings'),
    # path('chat/session/<uuid:session_id>/documents/', chat_views.add_documents_to_session, name='add_documents_to_session'),
    # path('chat/session/<uuid:session_id>/export/', chat_views.export_session, name='export_session'),
    # path('chat/session/<uuid:session_id>/stats/', chat_views.session_stats, name='session_stats'),
    # path('chat/session/<uuid:session_id>/delete/', chat_views.delete_session, name='delete_session'),
    # path('chat/send/', chat_views.send_message, name='send_message'),
    
    # API endpoints for AJAX/JSON responses  
    path('api/', include([
        # Document API
        path('documents/', views.api_document_list, name='api_document_list'),
        path('documents/<int:document_id>/', views.api_document_detail, name='api_document_detail'),
        path('documents/<int:document_id>/status/', views.document_status, name='api_document_status'),
        path('documents/<int:document_id>/process/', views.api_process_document, name='api_process_document'),
        path('documents/<int:document_id>/analysis/', views.api_document_analysis, name='api_document_analysis'),
        path('documents/<int:document_id>/download/', views.document_download, name='api_document_download'),
        path('search/', views.api_document_search, name='api_document_search'),
        
        # PDF Content Extraction API endpoints (temporarily disabled due to dependencies)
        # path('documents/<int:document_id>/extract-pdf/', api_views.extract_pdf_content, name='api_extract_pdf_content'),
        # path('documents/<int:document_id>/pdf-content/', api_views.get_pdf_content, name='api_get_pdf_content'),
        # path('documents/<int:document_id>/pdf-page/<int:page_number>/image/', api_views.get_pdf_page_image, name='api_get_pdf_page_image'),
        
        # Chat API (additional endpoints if needed) - Temporarily disabled
        # path('chat/sessions/', chat_views.api_chat_sessions, name='api_chat_sessions') if hasattr(chat_views, 'api_chat_sessions') else path('', lambda r: None),
        # path('chat/health/', chat_views.api_chat_health, name='api_chat_health') if hasattr(chat_views, 'api_chat_health') else path('', lambda r: None),
    ])),
    
    # Root API endpoints (accessible via /api/documents/)
    path('api/documents/', views.api_document_list, name='root_api_document_list'),
    path('api/documents/<int:document_id>/', views.api_document_detail, name='root_api_document_detail'),
    
    # Dashboard stats endpoint (temporary fix for CORS issue)
    path('api/dashboard/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
]