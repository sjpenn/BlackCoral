from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


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


@csrf_exempt
@require_http_methods(["GET"])
def api_dashboard_stats(request):
    """
    Simple dashboard stats API endpoint for frontend
    """
    return JsonResponse({
        'opportunities': {'total': 0, 'open': 0, 'closing_soon': 0, 'analyzed': 0},
        'teams': {'active_teams': 0, 'my_teams': 0, 'overdue_tasks': 0},
        'compliance': {'pending_reviews': 0, 'approved': 0},
        'ai_usage': {'requests_today': 0, 'total_tokens': 0},
        'user_activity': {'active_users': 1},
        'recent_activity': []
    })


@csrf_exempt
@require_http_methods(["GET"])
def api_documents_list(request):
    """
    Simple documents list API endpoint for frontend
    """
    return JsonResponse({
        'results': [],
        'count': 0,
        'next': None,
        'previous': None
    })