from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def compliance_dashboard(request):
    """
    Compliance monitoring dashboard - placeholder for Phase 3.
    """
    # Handle HTMX requests for authenticated users
    if request.headers.get('HX-Request') and not request.user.is_authenticated:
        response = HttpResponse()
        response['HX-Redirect'] = '/auth/login/'
        return response
        
    context = {
        'page_title': 'Compliance Monitoring'
    }
    return render(request, 'compliance/dashboard.html', context)