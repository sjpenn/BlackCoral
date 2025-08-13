from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


def landing_page(request):
    """
    Public landing page showcasing BLACK CORAL capabilities.
    """
    if request.user.is_authenticated:
        # Redirect authenticated users to dashboard
        return dashboard(request)
    
    context = {
        'page_title': 'BLACK CORAL - AI-Powered Government Contracting'
    }
    return render(request, 'core/landing.html', context)


@login_required
def dashboard(request):
    """
    Main dashboard view with role-specific widgets.
    """
    context = {
        'user_role': request.user.role if hasattr(request.user, 'role') else 'guest',
        'page_title': 'BLACK CORAL Dashboard'
    }
    return render(request, 'core/dashboard.html', context)


def health_check(request):
    """
    Health check endpoint for monitoring.
    """
    return JsonResponse({'status': 'healthy', 'service': 'BLACK CORAL'})