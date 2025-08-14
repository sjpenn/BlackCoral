from django.urls import path
from . import views

app_name = 'ai_integration'

urlpatterns = [
    path('', views.ai_dashboard, name='dashboard'),
    path('analyze/<int:opportunity_id>/', views.analyze_opportunity, name='analyze_opportunity'),
    path('compliance/<int:opportunity_id>/', views.check_compliance, name='check_compliance'),
    path('generate/<int:opportunity_id>/', views.generate_content, name='generate_content'),
    path('task/<int:task_id>/status/', views.task_status, name='task_status'),
    path('opportunity/<int:opportunity_id>/ai-data/', views.opportunity_ai_data, name='opportunity_ai_data'),
    path('test-providers/', views.test_providers, name='test_providers'),
]