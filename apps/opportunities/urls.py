from django.urls import path
from . import views

app_name = 'opportunities'

urlpatterns = [
    path('', views.opportunity_list, name='list'),
    path('<int:opportunity_id>/', views.opportunity_detail, name='detail'),
    path('refresh/', views.refresh_opportunities, name='refresh'),
    path('search-api/', views.search_opportunities_api, name='search_api'),
    path('stats/', views.opportunity_stats, name='stats'),
]