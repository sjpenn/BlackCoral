"""
URL configuration for BLACK CORAL project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core import views as core_views

# Helper function to check if app is installed
def is_app_installed(app_name):
    return app_name in settings.INSTALLED_APPS

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    
    # Authentication is always required
    path("auth/", include("apps.authentication.urls")),
    
    # API routes - simple endpoints  
    path("api/dashboard/stats/", core_views.api_dashboard_stats, name="api_dashboard_stats"),
    # Health check endpoint for Docker
    path("health/", core_views.health_check, name="health_check"),
]

# Conditionally add app URLs based on INSTALLED_APPS
if is_app_installed("apps.opportunities"):
    urlpatterns.append(path("opportunities/", include("apps.opportunities.urls")))
    
if is_app_installed("apps.documents"):
    urlpatterns.append(path("documents/", include("apps.documents.urls")))
    
if is_app_installed("apps.ai_integration"):
    urlpatterns.append(path("ai/", include("apps.ai_integration.urls")))
    
if is_app_installed("apps.compliance"):
    urlpatterns.append(path("compliance/", include("apps.compliance.urls")))
    
if is_app_installed("apps.collaboration"):
    urlpatterns.append(path("teams/", include("apps.collaboration.urls")))
    
if is_app_installed("apps.notifications"):
    urlpatterns.append(path("notifications/", include("apps.notifications.urls")))
    
if is_app_installed("apps.agents"):
    urlpatterns.append(path("agents/", include("apps.agents.urls")))
    
if is_app_installed("apps.salary_analysis"):
    urlpatterns.append(path("salary/", include("apps.salary_analysis.urls")))

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
