from django.urls import path
from . import views

app_name = 'opportunities'

urlpatterns = [
    # API endpoint that returns JSON (for React frontend)
    path('api/list/', views.opportunities_api, name='api_list'),
    
    # HTML views
    path('', views.opportunities_api, name='list'),  # Handle both API and HTML requests
    path('<int:opportunity_id>/', views.opportunity_detail, name='detail'),
    path('refresh/', views.refresh_opportunities, name='refresh'),
    path('search-api/', views.search_opportunities_api, name='search_api'),
    path('search-sam/', views.search_sam_gov, name='search_sam'),
    path('stats/', views.opportunity_stats, name='stats'),
    
    # SAM.gov opportunity management (specific routes first!)
    path('sam/bulk-save/', views.bulk_save_sam_opportunities, name='bulk_save_sam_opportunities'),
    path('sam/<str:notice_id>/', views.sam_opportunity_detail, name='sam_detail'),
    path('sam/<str:notice_id>/save/', views.save_sam_opportunity, name='save_sam_opportunity'),
    
    # AI Analysis endpoints (Legacy)
    path('sam/<str:notice_id>/analyze/', views.analyze_opportunity_with_ai, name='analyze_opportunity_ai'),
    path('sam/<str:notice_id>/share/', views.share_opportunity_via_email, name='share_opportunity_email'),
    path('sam/<str:notice_id>/analysis/', views.get_opportunity_analysis, name='get_opportunity_analysis'),
    path('ai/status/', views.get_ai_analysis_status, name='ai_analysis_status'),
    
    # Advanced AI Analysis endpoints
    path('sam/<str:notice_id>/ai-analysis/comprehensive/', views.comprehensive_ai_analysis, name='comprehensive_ai_analysis'),
    path('sam/<str:notice_id>/ai-analysis/targeted/', views.targeted_ai_analysis, name='targeted_ai_analysis'),
    path('sam/<str:notice_id>/ai-analysis/<str:analysis_id>/', views.ai_analysis_result, name='ai_analysis_result'),
    
    # Individual AI Tools endpoints
    path('sam/<str:notice_id>/ai-tools/past-performance-questionnaire/', views.generate_past_performance_questionnaire, name='generate_past_performance_questionnaire'),
    path('sam/<str:notice_id>/ai-tools/partner-selection/', views.analyze_partner_selection, name='analyze_partner_selection'),
    path('sam/<str:notice_id>/ai-tools/agency-priorities/', views.analyze_agency_priorities, name='analyze_agency_priorities'),
    
    # Search criteria management
    path('search/save/', views.save_search_criteria, name='save_search_criteria'),
    path('search/list/', views.list_search_criteria, name='list_search_criteria'),
    path('search/<int:criteria_id>/load/', views.load_search_criteria, name='load_search_criteria'),
    path('search/<int:criteria_id>/delete/', views.delete_search_criteria, name='delete_search_criteria'),
    
    # Document viewer endpoints
    path('document/view/<str:document_url>/', views.document_viewer, name='document_viewer'),
    path('document/proxy/<str:document_url>/', views.document_proxy, name='document_proxy'),
]