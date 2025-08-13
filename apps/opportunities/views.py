from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def opportunity_list(request):
    """
    List view for opportunities - placeholder for Phase 2.
    """
    # Handle HTMX requests for authenticated users
    if request.headers.get('HX-Request') and not request.user.is_authenticated:
        response = HttpResponse()
        response['HX-Redirect'] = '/auth/login/'
        return response
        
    context = {
        'page_title': 'Opportunities'
    }
    return render(request, 'opportunities/list.html', context)