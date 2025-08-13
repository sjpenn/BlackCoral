from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def ai_dashboard(request):
    """
    AI integration dashboard - placeholder for Phase 3.
    """
    # Handle HTMX requests for authenticated users
    if request.headers.get('HX-Request') and not request.user.is_authenticated:
        response = HttpResponse()
        response['HX-Redirect'] = '/auth/login/'
        return response
        
    context = {
        'page_title': 'AI Integration'
    }
    return render(request, 'ai_integration/dashboard.html', context)