"""
URL configuration for BLACK CORAL project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("auth/", include("apps.authentication.urls")),
    path("opportunities/", include("apps.opportunities.urls")),
    path("documents/", include("apps.documents.urls")),
    path("ai/", include("apps.ai_integration.urls")),
    path("compliance/", include("apps.compliance.urls")),
    path("teams/", include("apps.collaboration.urls")),
    path("notifications/", include("apps.notifications.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
