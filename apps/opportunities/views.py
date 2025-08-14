from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Opportunity
from .api_clients.sam_gov import SAMGovClient
from .tasks import fetch_new_opportunities, process_opportunity, analyze_opportunity_spending
from apps.core.models import NAICSCode, Agency


@login_required
def opportunity_list(request):
    """
    List and search opportunities with HTMX support.
    """
    # Handle HTMX requests for authenticated users
    if request.headers.get('HX-Request') and not request.user.is_authenticated:
        response = HttpResponse()
        response['HX-Redirect'] = '/auth/login/'
        return response
    
    # Get filter parameters
    search_term = request.GET.get('search', '')
    naics_filter = request.GET.get('naics', '')
    agency_filter = request.GET.get('agency', '')
    status_filter = request.GET.get('status', 'open')
    
    # Build queryset
    opportunities = Opportunity.objects.filter(is_active=True)
    
    # Apply filters
    if search_term:
        opportunities = opportunities.filter(
            Q(title__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(solicitation_number__icontains=search_term)
        )
    
    if naics_filter:
        opportunities = opportunities.filter(naics_codes__code=naics_filter)
    
    if agency_filter:
        opportunities = opportunities.filter(agency__id=agency_filter)
    
    if status_filter == 'open':
        opportunities = opportunities.filter(
            Q(response_date__gte=timezone.now()) | Q(response_date__isnull=True)
        )
    elif status_filter == 'closing_soon':
        soon = timezone.now() + timedelta(days=7)
        opportunities = opportunities.filter(
            response_date__lte=soon,
            response_date__gte=timezone.now()
        )
    
    # Order by posted date
    opportunities = opportunities.order_by('-posted_date')
    
    # Pagination
    paginator = Paginator(opportunities, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get filter options for dropdowns
    available_naics = NAICSCode.objects.filter(
        is_active=True,
        opportunity__is_active=True
    ).distinct()[:50]
    
    available_agencies = Agency.objects.filter(
        is_active=True,
        opportunity__is_active=True
    ).distinct()[:20]
    
    context = {
        'page_title': 'Government Contracting Opportunities',
        'opportunities': page_obj,
        'available_naics': available_naics,
        'available_agencies': available_agencies,
        'filters': {
            'search': search_term,
            'naics': naics_filter,
            'agency': agency_filter,
            'status': status_filter,
        },
        'total_count': paginator.count
    }
    
    # Return partial template for HTMX requests
    if request.headers.get('HX-Request'):
        if 'search' in request.GET or 'naics' in request.GET or 'agency' in request.GET or 'status' in request.GET:
            return render(request, 'opportunities/partials/opportunity_list.html', context)
    
    return render(request, 'opportunities/list.html', context)


@login_required
def opportunity_detail(request, opportunity_id):
    """
    Detailed view of a specific opportunity with USASpending analysis.
    """
    opportunity = get_object_or_404(Opportunity, id=opportunity_id, is_active=True)
    
    # Get related documents
    documents = opportunity.documents.all()
    
    # Get NAICS codes
    naics_codes = opportunity.naics_codes.all()
    
    # If USASpending analysis hasn't been done and user has permission, trigger it
    if not opportunity.usaspending_analyzed and request.user.can_research_opportunities:
        analyze_opportunity_spending.delay(opportunity.id)
    
    context = {
        'opportunity': opportunity,
        'documents': documents,
        'naics_codes': naics_codes,
        'usaspending_data': opportunity.usaspending_data,
        'page_title': f'Opportunity: {opportunity.title[:50]}'
    }
    
    return render(request, 'opportunities/detail.html', context)


@login_required
def refresh_opportunities(request):
    """
    HTMX endpoint to refresh opportunities from SAM.gov.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        # Trigger background task to fetch new opportunities
        task = fetch_new_opportunities.delay()
        
        return JsonResponse({
            'status': 'started',
            'task_id': task.id,
            'message': 'Refreshing opportunities from SAM.gov...'
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def search_opportunities_api(request):
    """
    Live search API endpoint for HTMX.
    """
    search_term = request.GET.get('q', '').strip()
    
    if len(search_term) < 2:
        return JsonResponse({'results': []})
    
    # Search in database first
    opportunities = Opportunity.objects.filter(
        Q(title__icontains=search_term) |
        Q(solicitation_number__icontains=search_term),
        is_active=True
    )[:10]
    
    results = []
    for opp in opportunities:
        results.append({
            'id': opp.id,
            'title': opp.title,
            'solicitation_number': opp.solicitation_number,
            'agency': opp.agency.name if opp.agency else 'Unknown',
            'posted_date': opp.posted_date.strftime('%Y-%m-%d'),
            'response_date': opp.response_date.strftime('%Y-%m-%d') if opp.response_date else None,
            'is_open': opp.is_open,
            'url': f'/opportunities/{opp.id}/'
        })
    
    return JsonResponse({'results': results})


@login_required
def opportunity_stats(request):
    """
    HTMX endpoint for opportunity statistics.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Calculate stats
    total_active = Opportunity.objects.filter(is_active=True).count()
    open_opportunities = Opportunity.objects.filter(
        is_active=True,
        response_date__gte=timezone.now()
    ).count()
    closing_soon = Opportunity.objects.filter(
        is_active=True,
        response_date__lte=timezone.now() + timedelta(days=7),
        response_date__gte=timezone.now()
    ).count()
    documents_processed = Opportunity.objects.filter(
        is_active=True,
        documents_fetched=True
    ).count()
    
    context = {
        'stats': {
            'total_active': total_active,
            'open_opportunities': open_opportunities,
            'closing_soon': closing_soon,
            'documents_processed': documents_processed,
        }
    }
    
    return render(request, 'opportunities/partials/stats.html', context)