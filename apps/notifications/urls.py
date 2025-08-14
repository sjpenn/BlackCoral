"""
BLACK CORAL Notification URLs
URL patterns for notification views and HTMX endpoints
"""

from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Main notification views
    path('', views.notification_center, name='center'),
    path('preferences/', views.notification_preferences, name='preferences'),
    path('digests/', views.notification_digests, name='digests'),
    path('digests/<int:digest_id>/', views.notification_digest_detail, name='digest_detail'),
    path('search/', views.notification_search, name='search'),
    
    # HTMX endpoints for real-time updates
    path('htmx/list/', views.notification_list_htmx, name='list_htmx'),
    path('htmx/badge/', views.notification_count_badge, name='badge_htmx'),
    path('htmx/dropdown/', views.notification_dropdown, name='dropdown_htmx'),
    path('htmx/poll/', views.notification_poll, name='poll_htmx'),
    
    # Notification actions
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('dismiss/<int:notification_id>/', views.dismiss_notification, name='dismiss'),
    
    # API endpoints
    path('api/webhook/', views.webhook_notification, name='webhook'),
    path('api/stats/', views.notification_stats, name='stats'),
]