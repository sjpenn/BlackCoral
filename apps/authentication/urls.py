from django.urls import path
from . import views, api_views

app_name = 'authentication'

urlpatterns = [
    # HTML views
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # API endpoints for Next.js frontend
    path('csrf/', api_views.get_csrf_token, name='csrf'),
    path('api/login/', api_views.api_login, name='api_login'),
    path('api/logout/', api_views.api_logout, name='api_logout'),
    path('api/user/', api_views.api_user_info, name='api_user_info'),
    path('api/status/', api_views.api_auth_status, name='api_auth_status'),
]