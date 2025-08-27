from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
import requests
import hashlib
from django.core.cache import cache
from django.conf import settings
from urllib.parse import urlparse
import mimetypes

from .models import Opportunity, SearchCriteria
from .api_clients.sam_gov import SAMGovClient
from .enhanced_sam_client import EnhancedSAMClient
from .ai_coordinator import AIAnalysisCoordinator
from .tasks import fetch_new_opportunities, process_opportunity, analyze_opportunity_spending
from apps.core.models import NAICSCode, Agency
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import logging
import json

logger = logging.getLogger('blackcoral.opportunities')


def is_authenticated_via_nextauth(request):
    """
    Check if user is authenticated via NextAuth session headers from API proxy.
    """
    return (
        request.headers.get('X-Authenticated') == 'true' and
        request.headers.get('X-User-Email')
    )

def opportunities_api(request):
    """
    REST API endpoint for opportunities - returns paginated JSON.
    Frontend expects: /api/opportunities/?page=1&page_size=10
    Can also handle HTML requests.
    """
    # Check Django authentication or NextAuth session headers
    if not (request.user.is_authenticated or is_authenticated_via_nextauth(request)):
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    # Check if this is an API request (has Accept: application/json or is from frontend)
    accept_header = request.headers.get('Accept', '')
    is_api_request = 'application/json' in accept_header or request.headers.get('User-Agent', '').startswith('Mozilla')
    
    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    
    # Get filter parameters
    search_term = request.GET.get('search', '')
    naics_filter = request.GET.get('naics', '')
    agency_filter = request.GET.get('agency', '')
    status_filter = request.GET.get('status', 'open')
    
    # Build queryset
    opportunities = Opportunity.objects.filter(is_active=True).select_related('agency')
    
    # Apply filters
    if search_term:
        opportunities = opportunities.filter(
            Q(title__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(agency__name__icontains=search_term)
        )
    
    if naics_filter:
        opportunities = opportunities.filter(naics_codes__code=naics_filter)
    
    if agency_filter:
        opportunities = opportunities.filter(agency__name__icontains=agency_filter)
    
    if status_filter == 'open':
        opportunities = opportunities.filter(response_date__gte=timezone.now().date())
    elif status_filter == 'closed':
        opportunities = opportunities.filter(response_date__lt=timezone.now().date())
    
    # Order by response date
    opportunities = opportunities.order_by('response_date')
    
    # Paginate
    paginator = Paginator(opportunities, page_size)
    page_obj = paginator.get_page(page)
    
    # Serialize data
    items = []
    for opp in page_obj:
        items.append({
            'id': opp.id,
            'title': opp.title,
            'description': opp.description[:200] + '...' if len(opp.description) > 200 else opp.description,
            'agency': opp.agency.name if opp.agency else None,
            'notice_id': opp.notice_id,
            'posted_date': opp.posted_date.isoformat() if opp.posted_date else None,
            'response_date': opp.response_date.isoformat() if opp.response_date else None,
            'award_amount': float(opp.award_amount) if opp.award_amount else None,
            'status': 'active' if opp.is_active else 'inactive',
            'aiAnalysis': None,  # TODO: Add AI analysis data when available
        })
    
    return JsonResponse({
        'items': items,
        'totalCount': paginator.count,
        'page': page,
        'pageSize': page_size,
        'totalPages': paginator.num_pages,
        'hasNext': page_obj.has_next(),
        'hasPrevious': page_obj.has_previous(),
    })


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
    
    # Build queryset with optimized relations
    opportunities = Opportunity.objects.filter(is_active=True).select_related(
        'agency'
    ).prefetch_related(
        'naics_codes',
        'documents'
    )
    
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
    Gracefully handles Celery/Redis unavailability.
    """
    if not request.user.can_research_opportunities:
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="alert alert-error">Permission denied</div>',
                status=403
            )
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            # Try to trigger background task
            task = fetch_new_opportunities.delay()
            
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    '<div class="alert alert-success">✓ Refreshing opportunities from SAM.gov...</div>'
                )
            
            return JsonResponse({
                'status': 'started',
                'task_id': task.id,
                'message': 'Refreshing opportunities from SAM.gov...'
            })
            
        except Exception as e:
            # Handle Redis/Celery connection errors gracefully
            error_msg = 'Background task service unavailable. Please try again later.'
            
            # Log the actual error for debugging
            import logging
            logger = logging.getLogger('blackcoral.opportunities')
            logger.error(f"Celery connection error in refresh_opportunities: {e}", exc_info=True)
            
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="alert alert-error">⚠ {error_msg}</div>',
                    status=200  # Return 200 to prevent HTMX error handling
                )
            
            return JsonResponse({
                'status': 'error',
                'message': error_msg,
                'fallback': 'The system is temporarily unable to connect to the background task service.'
            }, status=200)  # Changed from 503 to 200 for better HTMX handling
    
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
    HTMX endpoint for opportunity statistics with error handling.
    """
    if not request.user.can_research_opportunities:
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="alert alert-error">Permission denied</div>',
                status=403
            )
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Calculate stats with proper error handling
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
        
    except Exception as e:
        # Log error and return fallback stats
        import logging
        logger = logging.getLogger('blackcoral.opportunities')
        logger.error(f"Error calculating opportunity stats: {e}", exc_info=True)
        
        # Return fallback stats display
        context = {
            'stats': {
                'total_active': '—',
                'open_opportunities': '—',
                'closing_soon': '—',
                'documents_processed': '—',
            },
            'error': True
        }
        
        return render(request, 'opportunities/partials/stats.html', context)


@login_required
def search_sam_gov(request):
    """
    Direct search against SAM.gov API without relying on Celery.
    Supports NAICS code, title, and agency searches.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get search parameters
    search_type = request.GET.get('search_type', 'title')
    search_term = request.GET.get('q', '').strip()
    naics_code = request.GET.get('naics', '')
    agency = request.GET.get('agency', '')
    days_back = int(request.GET.get('days', '30'))
    
    # Pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = 10
    
    if not any([search_term, naics_code, agency]):
        return JsonResponse({
            'status': 'error',
            'message': 'Please provide at least one search parameter'
        })
    
    try:
        # Initialize SAM.gov client
        client = SAMGovClient()
        
        # Set date range
        posted_from = timezone.now() - timedelta(days=days_back)
        posted_to = timezone.now()
        
        # Build search parameters with pagination
        offset = (page - 1) * page_size
        search_params = {
            'limit': page_size,
            'offset': offset,
            'posted_from': posted_from,
            'posted_to': posted_to
        }
        
        # Add search criteria based on type
        if search_type == 'title' and search_term:
            search_params['title'] = search_term
        
        if naics_code:
            search_params['naics_codes'] = [naics_code]
        
        if agency:
            search_params['agencies'] = [agency]
        
        # Perform search
        logger.info(f"Performing SAM.gov search: {search_params}")
        result = client.search_opportunities(**search_params)
        
        opportunities = result.get('opportunities', [])
        
        # Process and save opportunities in background if any found
        if opportunities:
            try:
                for opp_data in opportunities[:10]:  # Process first 10 immediately
                    process_opportunity.delay(opp_data)
            except Exception as e:
                logger.warning(f"Could not queue opportunity processing: {e}")
        
        # Format response
        formatted_opportunities = []
        for opp in opportunities:
            formatted_opportunities.append({
                'notice_id': opp.get('noticeId', 'N/A'),
                'title': opp.get('title', 'Untitled'),
                'solicitation_number': opp.get('solicitationNumber', opp.get('noticeId', 'N/A')),
                'agency': opp.get('fullParentPathName', 'Unknown Agency'),
                'posted_date': opp.get('postedDate', 'N/A'),
                'response_date': opp.get('responseDeadLine', 'N/A'),
                'naics': opp.get('naicsCode', 'N/A'),
                'type': opp.get('type', 'N/A'),
                'set_aside': opp.get('typeOfSetAsideDescription', 'None'),
                'link': opp.get('uiLink', '#')
            })
        
        # Calculate pagination metadata
        total_records = result.get('api_total_records', 0)
        total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 1
        
        return JsonResponse({
            'status': 'success',
            'count': len(opportunities),
            'total_available': total_records,
            'opportunities': formatted_opportunities,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'page_size': page_size,
                'total_records': total_records,
                'has_next': page < total_pages,
                'has_previous': page > 1
            },
            'search_params': {
                'type': search_type,
                'term': search_term,
                'naics': naics_code,
                'agency': agency,
                'days_back': days_back
            }
        })
        
    except Exception as e:
        logger.error(f"SAM.gov search error: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Search failed: {str(e)}',
            'details': 'This may be due to API key issues or rate limits.'
        }, status=500)


@login_required
def sam_opportunity_detail(request, notice_id):
    """
    Display detailed view of a SAM.gov opportunity fetched live from the API.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Initialize SAM.gov client
        client = SAMGovClient()
        
        # Get opportunity details from SAM.gov API
        opportunity_data = client.get_opportunity_details(notice_id)
        
        # Fetch the full description text if the description field contains a URL
        description = opportunity_data.get('description', '')
        if description and description.startswith('https://api.sam.gov/prod/opportunities/v1/noticedesc'):
            logger.info(f"Fetching full description for notice {notice_id}")
            try:
                # Use the new method to fetch description by notice ID
                desc_result = client.fetch_opportunity_description_by_notice_id(notice_id)
                if desc_result.get('status') == 'ok':
                    opportunity_data['description'] = desc_result.get('description_text', '')
                    opportunity_data['descriptionFetched'] = True
                    logger.info(f"Successfully fetched description for {notice_id}")
                else:
                    error = desc_result.get('error', {})
                    logger.warning(f"Failed to fetch description: {error.get('message', 'Unknown error')}")
                    opportunity_data['descriptionError'] = error.get('message', 'Failed to fetch description')
                    opportunity_data['descriptionFetched'] = False
            except Exception as e:
                logger.error(f"Error fetching description for {notice_id}: {e}")
                opportunity_data['descriptionError'] = str(e)
                opportunity_data['descriptionFetched'] = False
        
        # Get enhanced document data with filename extraction
        documents = client.get_opportunity_documents(opportunity_data, extract_filenames=True)
        
        # Check if this opportunity already exists in our database
        existing_opportunity = Opportunity.objects.filter(notice_id=notice_id).first()
        
        context = {
            'opportunity_data': opportunity_data,
            'documents': documents,
            'existing_opportunity': existing_opportunity,
            'notice_id': notice_id,
            'page_title': opportunity_data.get('title', 'Opportunity Details')
        }
        
        return render(request, 'opportunities/sam_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error fetching SAM.gov opportunity {notice_id}: {e}", exc_info=True)
        return render(request, 'opportunities/sam_detail.html', {
            'error': f'Failed to fetch opportunity details: {str(e)}',
            'notice_id': notice_id,
            'page_title': 'Opportunity Details'
        })


@login_required
def save_sam_opportunity(request, notice_id):
    """
    Save a single SAM.gov opportunity to the local database.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Check if opportunity already exists
        if Opportunity.objects.filter(notice_id=notice_id).exists():
            return JsonResponse({
                'status': 'info',
                'message': 'Opportunity already exists in database'
            })
        
        # Get opportunity details from SAM.gov API
        client = SAMGovClient()
        opportunity_data = client.get_opportunity_details(notice_id)
        
        # Process the opportunity synchronously for immediate UI feedback
        # For save operations triggered from the UI, we want immediate results
        try:
            from .tasks import process_opportunity_sync
            result = process_opportunity_sync(opportunity_data)
            
            if result.get('status') == 'error':
                return JsonResponse({
                    'status': 'error',
                    'message': result.get('message', 'Failed to save opportunity')
                }, status=500)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Opportunity successfully saved to database'
            })
            
        except Exception as e:
            logger.error(f"Error processing opportunity synchronously: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to save opportunity: {str(e)}'
            }, status=500)
        
    except Exception as e:
        logger.error(f"Error saving SAM.gov opportunity {notice_id}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to save opportunity: {str(e)}'
        }, status=500)


@login_required
def bulk_save_sam_opportunities(request):
    """
    Save multiple SAM.gov opportunities to the local database.
    """
    logger.info(f"Bulk save request from user: {request.user.username} (role: {request.user.role})")
    logger.info(f"User can_research_opportunities: {request.user.can_research_opportunities}")
    
    if not request.user.can_research_opportunities:
        logger.warning(f"Permission denied for user {request.user.username}")
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        logger.info(f"Request body: {request.body}")
        data = json.loads(request.body)
        notice_ids = data.get('notice_ids', [])
        logger.info(f"Notice IDs to process: {notice_ids}")
        
        if not notice_ids:
            return JsonResponse({
                'status': 'error',
                'message': 'No opportunity IDs provided'
            })
        
        # Check which opportunities already exist
        existing_ids = set(Opportunity.objects.filter(
            notice_id__in=notice_ids
        ).values_list('notice_id', flat=True))
        
        new_ids = [nid for nid in notice_ids if nid not in existing_ids]
        
        if not new_ids:
            return JsonResponse({
                'status': 'info',
                'message': 'All selected opportunities already exist in database',
                'existing_count': len(existing_ids)
            })
        
        # Get opportunity details for new opportunities
        client = SAMGovClient()
        processed_count = 0
        
        for notice_id in new_ids:
            try:
                opportunity_data = client.get_opportunity_details(notice_id)
                process_opportunity.delay(opportunity_data)
                processed_count += 1
            except Exception as e:
                logger.warning(f"Failed to process opportunity {notice_id}: {e}")
                continue
        
        return JsonResponse({
            'status': 'success',
            'message': f'Queued {processed_count} opportunities for processing',
            'processed_count': processed_count,
            'existing_count': len(existing_ids),
            'total_requested': len(notice_ids)
        })
        
    except Exception as e:
        logger.error(f"Error bulk saving opportunities: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to save opportunities: {str(e)}'
        }, status=500)


@login_required
def save_search_criteria(request):
    """
    Save search criteria for future use.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Search name is required'
            })
        
        # Check if a search with this name already exists for this user
        if SearchCriteria.objects.filter(user=request.user, name=name).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'A search with this name already exists'
            })
        
        # Create the search criteria
        search_criteria = SearchCriteria.objects.create(
            user=request.user,
            name=name,
            search_term=data.get('search_term', ''),
            naics_codes=data.get('naics_codes', []),
            agencies=data.get('agencies', []),
            days_back=data.get('days_back', 30),
            is_favorite=data.get('is_favorite', False)
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Search criteria "{name}" saved successfully',
            'criteria_id': search_criteria.id
        })
        
    except Exception as e:
        logger.error(f"Error saving search criteria: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to save search criteria: {str(e)}'
        }, status=500)


@login_required
def load_search_criteria(request, criteria_id):
    """
    Load saved search criteria.
    """
    try:
        criteria = SearchCriteria.objects.get(id=criteria_id, user=request.user)
        
        # Update last_used timestamp
        criteria.last_used = timezone.now()
        criteria.save(update_fields=['last_used'])
        
        return JsonResponse({
            'status': 'success',
            'criteria': {
                'id': criteria.id,
                'name': criteria.name,
                'search_term': criteria.search_term,
                'naics_codes': criteria.naics_codes,
                'agencies': criteria.agencies,
                'days_back': criteria.days_back,
                'is_favorite': criteria.is_favorite
            }
        })
        
    except SearchCriteria.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Search criteria not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error loading search criteria: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to load search criteria: {str(e)}'
        }, status=500)


@login_required
def list_search_criteria(request):
    """
    List all saved search criteria for the current user.
    """
    try:
        criteria = SearchCriteria.objects.filter(user=request.user)
        
        criteria_list = []
        for c in criteria:
            criteria_list.append({
                'id': c.id,
                'name': c.name,
                'search_summary': c.search_summary,
                'is_favorite': c.is_favorite,
                'last_used': c.last_used.isoformat(),
                'created_at': c.created_at.isoformat()
            })
        
        return JsonResponse({
            'status': 'success',
            'criteria': criteria_list
        })
        
    except Exception as e:
        logger.error(f"Error listing search criteria: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to list search criteria: {str(e)}'
        }, status=500)


@login_required
def delete_search_criteria(request, criteria_id):
    """
    Delete saved search criteria.
    """
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        criteria = SearchCriteria.objects.get(id=criteria_id, user=request.user)
        criteria_name = criteria.name
        criteria.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Search criteria "{criteria_name}" deleted successfully'
        })
        
    except SearchCriteria.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Search criteria not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting search criteria: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to delete search criteria: {str(e)}'
        }, status=500)


@login_required
def document_viewer(request, document_url):
    """
    Document viewer that displays documents in-browser with PDF.js integration.
    Supports PDFs, text files, and other document formats.
    """
    try:
        # Decode and validate the document URL
        import base64
        from urllib.parse import unquote
        
        try:
            # URL is base64 encoded to handle special characters safely
            decoded_url = base64.urlsafe_b64decode(document_url.encode()).decode('utf-8')
        except Exception:
            # Fallback to direct URL decoding if base64 fails
            decoded_url = unquote(document_url)
        
        # Validate URL
        parsed_url = urlparse(decoded_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return HttpResponse("Invalid document URL", status=400)
        
        # Check if this is a SAM.gov document and add API key if needed
        if 'sam.gov' in parsed_url.netloc.lower():
            client = SAMGovClient()
            if client.api_key and 'api_key=' not in decoded_url:
                separator = '&' if '?' in decoded_url else '?'
                decoded_url = f"{decoded_url}{separator}api_key={client.api_key}"
        
        # Determine content type from URL or make a HEAD request
        content_type = mimetypes.guess_type(decoded_url)[0] or 'application/octet-stream'
        
        # For PDFs, use the PDF viewer template
        if content_type == 'application/pdf' or decoded_url.lower().endswith('.pdf'):
            return render(request, 'opportunities/document_viewer.html', {
                'document_url': decoded_url,
                'document_type': 'pdf',
                'page_title': 'Document Viewer - PDF'
            })
        
        # For text files, fetch and display content
        elif content_type.startswith('text/') or decoded_url.lower().endswith(('.txt', '.md', '.log')):
            try:
                content = fetch_document_content(decoded_url, max_size=1024*1024)  # 1MB limit
                return render(request, 'opportunities/document_viewer.html', {
                    'document_content': content,
                    'document_type': 'text',
                    'document_url': decoded_url,
                    'page_title': 'Document Viewer - Text'
                })
            except Exception as e:
                logger.warning(f"Failed to fetch text content: {e}")
                return render(request, 'opportunities/document_viewer.html', {
                    'document_url': decoded_url,
                    'document_type': 'external',
                    'error': 'Failed to load document content',
                    'page_title': 'Document Viewer'
                })
        
        # For other document types, use iframe or external link
        else:
            return render(request, 'opportunities/document_viewer.html', {
                'document_url': decoded_url,
                'document_type': 'external',
                'page_title': 'Document Viewer'
            })
            
    except Exception as e:
        logger.error(f"Error in document viewer: {e}", exc_info=True)
        return HttpResponse("Error loading document", status=500)


@login_required
def document_proxy(request, document_url):
    """
    Secure proxy for external documents to handle CORS and authentication.
    Streams document content while adding security headers.
    """
    try:
        # Decode and validate the document URL
        import base64
        from urllib.parse import unquote
        
        try:
            decoded_url = base64.urlsafe_b64decode(document_url.encode()).decode('utf-8')
        except Exception:
            decoded_url = unquote(document_url)
        
        # Validate URL
        parsed_url = urlparse(decoded_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return HttpResponse("Invalid document URL", status=400)
        
        # Add API key for SAM.gov documents
        if 'sam.gov' in parsed_url.netloc.lower():
            client = SAMGovClient()
            if client.api_key and 'api_key=' not in decoded_url:
                separator = '&' if '?' in decoded_url else '?'
                decoded_url = f"{decoded_url}{separator}api_key={client.api_key}"
        
        # Check cache first
        cache_key = f"document_proxy:{hashlib.md5(decoded_url.encode()).hexdigest()}"
        cached_response = cache.get(cache_key)
        
        if cached_response and len(cached_response.get('content', '')) < 1024 * 1024:  # Cache only files < 1MB
            response = HttpResponse(
                cached_response['content'],
                content_type=cached_response.get('content_type', 'application/octet-stream')
            )
            response['Content-Length'] = len(cached_response['content'])
            return response
        
        # Fetch document
        headers = {
            'User-Agent': 'BLACK CORAL Government Contracting System',
            'Accept': '*/*'
        }
        
        # Stream the response
        with requests.get(decoded_url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            
            content_type = r.headers.get('content-type', 'application/octet-stream')
            content_length = r.headers.get('content-length')
            
            # For small files, cache the content
            if content_length and int(content_length) < 1024 * 1024:  # 1MB
                content = b''.join(chunk for chunk in r.iter_content(chunk_size=8192))
                cache.set(cache_key, {
                    'content': content,
                    'content_type': content_type
                }, timeout=3600)  # Cache for 1 hour
                
                response = HttpResponse(content, content_type=content_type)
                response['Content-Length'] = len(content)
            else:
                # Stream large files
                response = StreamingHttpResponse(
                    r.iter_content(chunk_size=8192),
                    content_type=content_type
                )
                if content_length:
                    response['Content-Length'] = content_length
            
            # Add security headers
            response['X-Frame-Options'] = 'SAMEORIGIN'
            response['X-Content-Type-Options'] = 'nosniff'
            
            return response
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching document via proxy: {e}")
        return HttpResponse("Error fetching document", status=502)
    except Exception as e:
        logger.error(f"Error in document proxy: {e}", exc_info=True)
        return HttpResponse("Error loading document", status=500)


def fetch_document_content(url, max_size=1024*1024):
    """
    Helper function to fetch text content from a URL with size limits.
    """
    headers = {
        'User-Agent': 'BLACK CORAL Government Contracting System',
        'Accept': 'text/plain,text/html,text/*,*/*'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Check content length
    if response.headers.get('content-length'):
        content_length = int(response.headers['content-length'])
        if content_length > max_size:
            raise ValueError(f"Document too large: {content_length} bytes")
    
    content = response.text
    if len(content.encode('utf-8')) > max_size:
        content = content[:max_size] + '\n\n... (content truncated)'
    
    return content


@login_required
@require_http_methods(["POST"])
def analyze_opportunity_with_ai(request, notice_id):
    """
    Run AI analysis on a SAM.gov opportunity using the 7 core tools.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        import json
        request_data = json.loads(request.body) if request.body else {}
        analysis_types = request_data.get('analysis_types', [])
        
        # Initialize enhanced SAM client
        client = EnhancedSAMClient()
        
        # Get opportunity details first
        try:
            opportunity_data = client.get_opportunity_details(notice_id)
        except Exception as e:
            logger.error(f"Failed to fetch opportunity {notice_id}: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to fetch opportunity details: {str(e)}'
            }, status=400)
        
        # Run AI analysis
        logger.info(f"Starting AI analysis for opportunity {notice_id}")
        analysis_results = client.analyze_opportunity_with_ai(
            opportunity_data=opportunity_data,
            user=request.user,
            analysis_types=analysis_types if analysis_types else None
        )
        
        # Save analysis results to opportunity if it exists in database
        try:
            opportunity = Opportunity.objects.get(notice_id=notice_id)
            opportunity.ai_analysis_data = analysis_results
            opportunity.ai_analysis_complete = len(analysis_results.get('errors', [])) == 0
            opportunity.save(update_fields=['ai_analysis_data', 'ai_analysis_complete'])
            logger.info(f"Saved AI analysis results to opportunity {notice_id}")
        except Opportunity.DoesNotExist:
            logger.info(f"Opportunity {notice_id} not in database, analysis results not saved")
        except Exception as e:
            logger.warning(f"Failed to save analysis results: {e}")
        
        return JsonResponse({
            'status': 'success',
            'analysis_results': analysis_results,
            'message': f'AI analysis completed for opportunity {notice_id}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"AI analysis failed for opportunity {notice_id}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'AI analysis failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def share_opportunity_via_email(request, notice_id):
    """
    Share opportunity and analysis results via email.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        import json
        request_data = json.loads(request.body)
        
        recipient_emails = request_data.get('recipients', [])
        custom_message = request_data.get('message', '')
        include_analysis = request_data.get('include_analysis', True)
        include_attachments = request_data.get('include_attachments', True)
        
        if not recipient_emails:
            return JsonResponse({
                'status': 'error',
                'message': 'At least one recipient email is required'
            }, status=400)
        
        # Validate email addresses
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        
        for email in recipient_emails:
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid email address: {email}'
                }, status=400)
        
        # Initialize enhanced SAM client
        client = EnhancedSAMClient()
        
        # Get opportunity details
        try:
            opportunity_data = client.get_opportunity_details(notice_id)
        except Exception as e:
            logger.error(f"Failed to fetch opportunity {notice_id}: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to fetch opportunity details: {str(e)}'
            }, status=400)
        
        # Get analysis results if requested
        analysis_results = None
        if include_analysis:
            try:
                # First try to get from database
                opportunity = Opportunity.objects.get(notice_id=notice_id)
                if opportunity.ai_analysis_data:
                    analysis_results = opportunity.ai_analysis_data
                    logger.info(f"Using existing analysis results for {notice_id}")
                else:
                    logger.info(f"No existing analysis found for {notice_id}, running new analysis")
                    # Run basic analysis for sharing
                    analysis_results = client.analyze_opportunity_with_ai(
                        opportunity_data=opportunity_data,
                        user=request.user,
                        analysis_types=['opportunity_analysis', 'bid_recommendation']
                    )
            except Opportunity.DoesNotExist:
                logger.info(f"Opportunity {notice_id} not in database, running analysis for sharing")
                # Run basic analysis for sharing
                analysis_results = client.analyze_opportunity_with_ai(
                    opportunity_data=opportunity_data,
                    user=request.user,
                    analysis_types=['opportunity_analysis', 'bid_recommendation']
                )
            except Exception as e:
                logger.warning(f"Failed to get analysis for sharing: {e}")
                # Continue without analysis
        
        # Send email
        logger.info(f"Sharing opportunity {notice_id} via email to {len(recipient_emails)} recipients")
        sharing_results = client.share_opportunity_via_email(
            opportunity_data=opportunity_data,
            analysis_results=analysis_results,
            recipient_emails=recipient_emails,
            sender_user=request.user,
            custom_message=custom_message,
            include_attachments=include_attachments
        )
        
        if sharing_results['success']:
            return JsonResponse({
                'status': 'success',
                'sharing_results': sharing_results,
                'message': f'Opportunity shared successfully with {len(recipient_emails)} recipients'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'sharing_results': sharing_results,
                'message': f'Failed to share opportunity: {"; ".join(sharing_results.get("errors", []))}'
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Email sharing failed for opportunity {notice_id}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Email sharing failed: {str(e)}'
        }, status=500)


@login_required
def get_opportunity_analysis(request, notice_id):
    """
    Get existing AI analysis results for an opportunity.
    """
    if not request.user.can_research_opportunities:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Try to get from database first
        try:
            opportunity = Opportunity.objects.get(notice_id=notice_id)
            if opportunity.ai_analysis_data:
                return JsonResponse({
                    'status': 'success',
                    'analysis_results': opportunity.ai_analysis_data,
                    'analysis_complete': opportunity.ai_analysis_complete,
                    'source': 'database'
                })
        except Opportunity.DoesNotExist:
            pass
        
        return JsonResponse({
            'status': 'not_found',
            'message': 'No analysis results found for this opportunity'
        }, status=404)
        
    except Exception as e:
        logger.error(f"Failed to get analysis for opportunity {notice_id}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to get analysis results: {str(e)}'
        }, status=500)


@login_required
def get_ai_analysis_status(request):
    """
    Get AI analysis capabilities and status.
    """
    try:
        from apps.ai_integration.ai_providers import ai_manager
        
        available_providers = ai_manager.get_available_providers()
        model_info = ai_manager.get_model_info()
        
        analysis_tools = [
            {
                'id': 'opportunity_analysis',
                'name': 'Opportunity Analysis',
                'description': 'Comprehensive opportunity assessment with technical requirements, business opportunity, and recommendations',
                'category': 'Core Analysis'
            },
            {
                'id': 'compliance_check',
                'name': 'Compliance Check',
                'description': 'Regulatory compliance analysis and requirements validation',
                'category': 'Core Analysis'
            },
            {
                'id': 'risk_assessment',
                'name': 'Risk Assessment',
                'description': 'Risk identification and mitigation strategy development',
                'category': 'Core Analysis'
            },
            {
                'id': 'competitive_analysis',
                'name': 'Competitive Analysis',
                'description': 'Market intelligence and competitive landscape analysis',
                'category': 'Core Analysis'
            },
            {
                'id': 'proposal_outline',
                'name': 'Proposal Outline',
                'description': 'AI-generated proposal structure and outline',
                'category': 'Content Generation'
            },
            {
                'id': 'executive_summary',
                'name': 'Executive Summary',
                'description': 'Executive summary generation for decision makers',
                'category': 'Content Generation'
            },
            {
                'id': 'bid_recommendation',
                'name': 'Bid Recommendation',
                'description': 'Go/No-go recommendation with strategic rationale',
                'category': 'Decision Support'
            },
            # New Advanced AI Tools
            {
                'id': 'past_performance_questionnaires',
                'name': 'Past Performance Questionnaires',
                'description': 'Generate tailored past performance questionnaires based on opportunity requirements',
                'category': 'Advanced Tools',
                'confidence_scoring': True
            },
            {
                'id': 'partner_selection',
                'name': 'Partner Selection Analysis',
                'description': 'Identify and rank potential teaming partners with capability gap analysis',
                'category': 'Advanced Tools',
                'confidence_scoring': True
            },
            {
                'id': 'agency_priority_analysis',
                'name': 'Agency Priority Analysis',
                'description': 'Analyze agency preferences and historical procurement patterns',
                'category': 'Advanced Tools',
                'confidence_scoring': True
            },
            {
                'id': 'enhanced_summary',
                'name': 'Enhanced Summary Analysis',
                'description': 'Strategic opportunity summary with win themes and competitive positioning',
                'category': 'Enhanced Tools',
                'confidence_scoring': True
            },
            {
                'id': 'enhanced_capture',
                'name': 'Enhanced Capture Planning',
                'description': 'Comprehensive capture strategy with stakeholder analysis and positioning',
                'category': 'Enhanced Tools',
                'confidence_scoring': True
            },
            {
                'id': 'enhanced_capability_matrix',
                'name': 'Enhanced Capability Matrix',
                'description': 'Detailed capability analysis with gap recommendations and improvement strategies',
                'category': 'Enhanced Tools',
                'confidence_scoring': True
            }
        ]
        
        return JsonResponse({
            'status': 'success',
            'ai_enabled': len(available_providers) > 0,
            'available_providers': [p.value for p in available_providers],
            'model_info': model_info,
            'analysis_tools': analysis_tools,
            'total_tools': len(analysis_tools)
        })
        
    except Exception as e:
        logger.error(f"Failed to get AI analysis status: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to get AI status: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def comprehensive_ai_analysis(request, notice_id):
    """
    Run comprehensive AI analysis using the AI Analysis Coordinator.
    
    POST /api/opportunities/{notice_id}/ai-analysis/comprehensive/
    """
    try:
        # Get opportunity data
        sam_client = EnhancedSAMClient()
        opportunity_data = sam_client.get_opportunity_by_notice_id(notice_id)
        
        if not opportunity_data:
            return JsonResponse({
                'status': 'error',
                'message': f'Opportunity {notice_id} not found'
            }, status=404)
        
        # Parse request parameters
        data = json.loads(request.body) if request.body else {}
        workflow_type = data.get('workflow_type', 'standard')
        include_enhanced_tools = data.get('include_enhanced_tools', True)
        
        # Initialize AI coordinator
        coordinator = AIAnalysisCoordinator()
        
        # Customize workflow based on parameters
        if include_enhanced_tools:
            workflow_type = 'high_value'  # Use high-value config for enhanced analysis
        
        # Run comprehensive analysis
        logger.info(f"Starting comprehensive AI analysis for {notice_id} with workflow: {workflow_type}")
        
        result = coordinator.analyze_opportunity_comprehensive(
            opportunity_data=opportunity_data,
            user=request.user,
            workflow_type=workflow_type
        )
        
        # Format response
        response_data = {
            'status': 'success',
            'opportunity_id': result.opportunity_id,
            'analysis_results': result.analysis_results,
            'execution_metadata': result.execution_metadata,
            'quality_metrics': result.quality_metrics,
            'recommendations': result.recommendations,
            'overall_confidence': result.overall_confidence,
            'success_rate': result.success_rate,
            'generated_at': result.generated_at.isoformat()
        }
        
        logger.info(f"Comprehensive AI analysis completed for {notice_id}. "
                   f"Success rate: {result.success_rate:.1%}, "
                   f"Confidence: {result.overall_confidence:.1%}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Comprehensive AI analysis failed for {notice_id}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Analysis failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def targeted_ai_analysis(request, notice_id):
    """
    Run targeted AI analysis focused on specific goals.
    
    POST /api/opportunities/{notice_id}/ai-analysis/targeted/
    Body: {"analysis_goals": ["bid_decision", "teaming_strategy"]}
    """
    try:
        # Get opportunity data
        sam_client = EnhancedSAMClient()
        opportunity_data = sam_client.get_opportunity_by_notice_id(notice_id)
        
        if not opportunity_data:
            return JsonResponse({
                'status': 'error',
                'message': f'Opportunity {notice_id} not found'
            }, status=404)
        
        # Parse request parameters
        data = json.loads(request.body)
        analysis_goals = data.get('analysis_goals', ['bid_decision'])
        
        # Validate analysis goals
        valid_goals = [
            'bid_decision', 'teaming_strategy', 'compliance_readiness',
            'capture_planning', 'proposal_preparation'
        ]
        
        invalid_goals = [goal for goal in analysis_goals if goal not in valid_goals]
        if invalid_goals:
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid analysis goals: {invalid_goals}. Valid goals: {valid_goals}'
            }, status=400)
        
        # Initialize AI coordinator
        coordinator = AIAnalysisCoordinator()
        
        # Run targeted analysis
        logger.info(f"Starting targeted AI analysis for {notice_id} with goals: {analysis_goals}")
        
        result = coordinator.analyze_opportunity_targeted(
            opportunity_data=opportunity_data,
            analysis_goals=analysis_goals,
            user=request.user
        )
        
        # Format response
        response_data = {
            'status': 'success',
            'opportunity_id': result.opportunity_id,
            'analysis_goals': analysis_goals,
            'analysis_results': result.analysis_results,
            'execution_metadata': result.execution_metadata,
            'quality_metrics': result.quality_metrics,
            'recommendations': result.recommendations,
            'overall_confidence': result.overall_confidence,
            'success_rate': result.success_rate,
            'generated_at': result.generated_at.isoformat()
        }
        
        logger.info(f"Targeted AI analysis completed for {notice_id}. "
                   f"Goals: {analysis_goals}, Success rate: {result.success_rate:.1%}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Targeted AI analysis failed for {notice_id}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Analysis failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def ai_analysis_result(request, notice_id, analysis_id):
    """
    Retrieve stored AI analysis results.
    
    GET /api/opportunities/{notice_id}/ai-analysis/{analysis_id}/
    """
    try:
        # For now, return cached results or database lookup
        # In production, you might store analysis results in the database
        cache_key = f"ai_analysis_{notice_id}_{analysis_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return JsonResponse({
                'status': 'success',
                'result': cached_result
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Analysis result not found or expired'
            }, status=404)
            
    except Exception as e:
        logger.error(f"Failed to retrieve AI analysis result: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to retrieve result: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def generate_past_performance_questionnaire(request, notice_id):
    """
    Generate tailored past performance questionnaire.
    
    POST /api/opportunities/{notice_id}/ai-tools/past-performance-questionnaire/
    """
    try:
        # Get opportunity data
        sam_client = EnhancedSAMClient()
        opportunity_data = sam_client.get_opportunity_by_notice_id(notice_id)
        
        if not opportunity_data:
            return JsonResponse({
                'status': 'error',
                'message': f'Opportunity {notice_id} not found'
            }, status=404)
        
        # Parse request parameters
        data = json.loads(request.body) if request.body else {}
        company_profile = data.get('company_profile', getattr(request.user, 'company_profile', None))
        
        # Initialize AI coordinator and run analysis
        coordinator = AIAnalysisCoordinator()
        
        result = coordinator.ai_tools.generate_past_performance_questionnaire(
            opportunity_data=opportunity_data,
            company_profile=company_profile
        )
        
        # Format response
        response_data = {
            'status': 'success',
            'opportunity_id': result.opportunity_id,
            'agency': result.agency,
            'questionnaire': {
                'key_requirements': result.key_requirements,
                'questions': result.questions,
                'evaluation_criteria': result.evaluation_criteria,
                'submission_guidelines': result.submission_guidelines,
                'questions_count': len(result.questions)
            },
            'confidence_score': result.confidence_score,
            'generated_at': result.generated_at.isoformat()
        }
        
        logger.info(f"Past performance questionnaire generated for {notice_id} "
                   f"with {len(result.questions)} questions")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Past performance questionnaire generation failed: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Questionnaire generation failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def analyze_partner_selection(request, notice_id):
    """
    Analyze potential teaming partners for the opportunity.
    
    POST /api/opportunities/{notice_id}/ai-tools/partner-selection/
    """
    try:
        # Get opportunity data
        sam_client = EnhancedSAMClient()
        opportunity_data = sam_client.get_opportunity_by_notice_id(notice_id)
        
        if not opportunity_data:
            return JsonResponse({
                'status': 'error',
                'message': f'Opportunity {notice_id} not found'
            }, status=404)
        
        # Parse request parameters
        data = json.loads(request.body) if request.body else {}
        company_capabilities = data.get('company_capabilities', getattr(request.user, 'company_capabilities', None))
        market_intelligence = data.get('market_intelligence')
        
        # Initialize AI coordinator and run analysis
        coordinator = AIAnalysisCoordinator()
        
        result = coordinator.ai_tools.analyze_partner_selection(
            opportunity_data=opportunity_data,
            company_capabilities=company_capabilities,
            market_intelligence=market_intelligence
        )
        
        # Format response
        response_data = {
            'status': 'success',
            'opportunity_id': result.opportunity_id,
            'partner_analysis': {
                'recommended_partners': result.recommended_partners,
                'partnership_strategies': result.partnership_strategies,
                'capability_gaps': result.capability_gaps,
                'teaming_recommendations': result.teaming_recommendations,
                'market_intelligence': result.market_intelligence,
                'partners_count': len(result.recommended_partners)
            },
            'confidence_score': result.confidence_score,
            'generated_at': result.generated_at.isoformat()
        }
        
        logger.info(f"Partner selection analysis completed for {notice_id} "
                   f"with {len(result.recommended_partners)} partner recommendations")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Partner selection analysis failed: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Partner analysis failed: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def analyze_agency_priorities(request, notice_id):
    """
    Analyze agency priorities and procurement patterns.
    
    POST /api/opportunities/{notice_id}/ai-tools/agency-priorities/
    """
    try:
        # Get opportunity data
        sam_client = EnhancedSAMClient()
        opportunity_data = sam_client.get_opportunity_by_notice_id(notice_id)
        
        if not opportunity_data:
            return JsonResponse({
                'status': 'error',
                'message': f'Opportunity {notice_id} not found'
            }, status=404)
        
        # Parse request parameters
        data = json.loads(request.body) if request.body else {}
        historical_data = data.get('historical_data')
        
        # Initialize AI coordinator and run analysis
        coordinator = AIAnalysisCoordinator()
        
        result = coordinator.ai_tools.analyze_agency_priorities(
            opportunity_data=opportunity_data,
            historical_data=historical_data
        )
        
        # Format response
        response_data = {
            'status': 'success',
            'agency_name': result.agency_name,
            'agency_analysis': {
                'historical_patterns': result.historical_patterns,
                'procurement_preferences': result.procurement_preferences,
                'key_decision_makers': result.key_decision_makers,
                'success_factors': result.success_factors,
                'risk_factors': result.risk_factors,
                'strategic_recommendations': result.strategic_recommendations,
                'priority_score': result.priority_score
            },
            'confidence_score': result.confidence_score,
            'generated_at': result.generated_at.isoformat()
        }
        
        logger.info(f"Agency priority analysis completed for {result.agency_name}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Agency priority analysis failed: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Agency analysis failed: {str(e)}'
        }, status=500)