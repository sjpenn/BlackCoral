"""
Celery tasks for opportunity management.
Handles fetching, processing, and updating opportunities from SAM.gov.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import shared_task, chord, group
from django.utils import timezone
from django.db import transaction

from .models import Opportunity
from .api_clients.sam_gov import SAMGovClient, SAMGovAPIError
from .api_clients.usaspending_gov import USASpendingClient
from apps.core.models import NAICSCode, Agency
from apps.documents.tasks import fetch_opportunity_documents

logger = logging.getLogger('blackcoral.opportunities.tasks')


@shared_task(bind=True, max_retries=3)
def fetch_new_opportunities(self):
    """
    Fetch new opportunities from SAM.gov API.
    Runs hourly during business hours.
    """
    try:
        client = SAMGovClient()
        
        # Fetch opportunities from the last 7 days
        posted_from = timezone.now() - timedelta(days=7)
        posted_to = timezone.now()
        
        # Get active NAICS codes we're interested in
        active_naics = list(NAICSCode.objects.filter(
            is_active=True
        ).values_list('code', flat=True))
        
        logger.info(f"Fetching opportunities for {len(active_naics)} NAICS codes")
        
        # Fetch in batches to handle pagination
        all_opportunities = []
        offset = 0
        limit = 100
        
        while True:
            try:
                result = client.search_opportunities(
                    limit=limit,
                    offset=offset,
                    posted_from=posted_from,
                    posted_to=posted_to,
                    naics_codes=active_naics if active_naics else None
                )
                
                opportunities = result.get('opportunities', [])
                if not opportunities:
                    break
                
                all_opportunities.extend(opportunities)
                
                # Check if we've fetched all available
                if len(opportunities) < limit:
                    break
                
                offset += limit
                
            except SAMGovAPIError as e:
                if "rate limit" in str(e).lower():
                    logger.warning("Rate limit reached, will retry later")
                    break
                raise
        
        logger.info(f"Fetched {len(all_opportunities)} opportunities")
        
        # Process opportunities in parallel
        if all_opportunities:
            job = group(
                process_opportunity.s(opp_data) for opp_data in all_opportunities
            )
            job.apply_async()
        
        return {
            'status': 'success',
            'count': len(all_opportunities),
            'posted_from': posted_from.isoformat(),
            'posted_to': posted_to.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching opportunities: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry in 5 minutes


@shared_task(bind=True, max_retries=3)
def process_opportunity(self, opportunity_data: Dict[str, Any]):
    """
    Process a single opportunity from SAM.gov.
    Creates or updates the opportunity in the database.
    """
    try:
        notice_id = opportunity_data.get('noticeId')
        if not notice_id:
            logger.error("Opportunity missing noticeId")
            return
        
        # Get or create agency
        agency = None
        if opportunity_data.get('fullParentPathName'):
            agency_name = opportunity_data['fullParentPathName'].split('.')[-1]
            agency, _ = Agency.objects.get_or_create(
                abbreviation=agency_name[:20],
                defaults={'name': agency_name}
            )
        
        # Parse dates
        posted_date = None
        if opportunity_data.get('postedDate'):
            try:
                posted_date = datetime.strptime(
                    opportunity_data['postedDate'], 
                    '%m/%d/%Y'
                ).date()
            except ValueError:
                logger.warning(f"Invalid posted date: {opportunity_data['postedDate']}")
        
        response_date = None
        if opportunity_data.get('responseDeadLine'):
            try:
                response_date = datetime.strptime(
                    opportunity_data['responseDeadLine'],
                    '%m/%d/%Y'
                ).date()
            except ValueError:
                logger.warning(f"Invalid response date: {opportunity_data['responseDeadLine']}")
        
        # Create or update opportunity
        with transaction.atomic():
            opportunity, created = Opportunity.objects.update_or_create(
                solicitation_number=notice_id,
                defaults={
                    'title': opportunity_data.get('title', '')[:500],
                    'description': opportunity_data.get('description', ''),
                    'agency': agency,
                    'posted_date': posted_date or timezone.now(),
                    'response_date': response_date,
                    'source_url': opportunity_data.get('uiLink', ''),
                    'source_api': 'sam.gov',
                    'raw_data': opportunity_data,  # Store full response
                    'opportunity_type': opportunity_data.get('type', ''),
                    'set_aside_type': opportunity_data.get('typeOfSetAsideDescription', ''),
                    'place_of_performance': opportunity_data.get('placeOfPerformance', {}),
                    'point_of_contact': opportunity_data.get('pointOfContact', {}),
                }
            )
            
            # Add NAICS codes
            if opportunity_data.get('naicsCode'):
                try:
                    naics = NAICSCode.objects.get(code=opportunity_data['naicsCode'])
                    opportunity.naics_codes.add(naics)
                except NAICSCode.DoesNotExist:
                    logger.warning(f"NAICS code not found: {opportunity_data['naicsCode']}")
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} opportunity: {notice_id}")
        
        # Fetch documents if new opportunity
        if created:
            fetch_opportunity_documents.delay(opportunity.id)
        
        return {
            'status': 'success',
            'notice_id': notice_id,
            'action': action.lower()
        }
        
    except Exception as e:
        logger.error(f"Error processing opportunity {opportunity_data.get('noticeId')}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def fetch_opportunity_details(self, opportunity_id: int):
    """
    Fetch detailed information for a specific opportunity.
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        client = SAMGovClient()
        
        # Fetch latest details
        details = client.get_opportunity_details(opportunity.solicitation_number)
        
        # Update opportunity with latest data
        opportunity.raw_data = details
        opportunity.save()
        
        # Extract any new document links
        documents = client.get_opportunity_documents(details)
        if documents:
            fetch_opportunity_documents.delay(opportunity_id, documents)
        
        return {
            'status': 'success',
            'opportunity_id': opportunity_id,
            'documents_found': len(documents)
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error fetching opportunity details: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def update_opportunity_naics_matches():
    """
    Update NAICS code matches for opportunities based on capability sets.
    """
    from apps.core.models import CapabilitySet
    
    # Get all active capability sets
    capability_sets = CapabilitySet.objects.filter(is_active=True).prefetch_related('naics_codes')
    
    for capability_set in capability_sets:
        naics_codes = list(capability_set.naics_codes.values_list('code', flat=True))
        
        # Find matching opportunities
        matching_opportunities = Opportunity.objects.filter(
            naics_codes__code__in=naics_codes,
            is_active=True
        ).distinct()
        
        # Tag opportunities with capability set
        for opportunity in matching_opportunities:
            if not hasattr(opportunity, 'capability_matches'):
                opportunity.capability_matches = []
            opportunity.capability_matches.append(capability_set.name)
            opportunity.save()
    
    return {
        'status': 'success',
        'capability_sets_processed': capability_sets.count()
    }


@shared_task(bind=True, max_retries=3)
def analyze_opportunity_spending(self, opportunity_id: int):
    """
    Analyze opportunity using USASpending.gov data for context.
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        usaspending_client = USASpendingClient()
        
        # Prepare opportunity data for analysis
        opportunity_data = {
            'naics_codes': list(opportunity.naics_codes.values_list('code', flat=True)),
            'agency_name': opportunity.agency.name if opportunity.agency else None,
            'solicitation_number': opportunity.solicitation_number,
            'title': opportunity.title,
            'description': opportunity.description
        }
        
        # Perform USASpending analysis
        analysis = usaspending_client.analyze_opportunity_context(opportunity_data)
        
        # Store analysis results
        opportunity.usaspending_data = analysis
        opportunity.usaspending_analyzed = True
        opportunity.save()
        
        logger.info(f"USASpending analysis completed for opportunity {opportunity_id}")
        
        return {
            'status': 'success',
            'opportunity_id': opportunity_id,
            'analysis_components': list(analysis.keys())
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found for USASpending analysis")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error analyzing opportunity {opportunity_id} with USASpending: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def bulk_analyze_opportunities_spending(limit: int = 50):
    """
    Analyze multiple opportunities that haven't been analyzed with USASpending data.
    """
    opportunities = Opportunity.objects.filter(
        usaspending_analyzed=False,
        is_active=True
    ).order_by('-posted_date')[:limit]
    
    if not opportunities:
        return {
            'status': 'success',
            'message': 'No opportunities need USASpending analysis',
            'processed': 0
        }
    
    # Create group of analysis tasks
    analysis_tasks = group([
        analyze_opportunity_spending.s(opp.id) 
        for opp in opportunities
    ])
    
    # Execute tasks
    result = analysis_tasks.apply_async()
    
    logger.info(f"Started USASpending analysis for {len(opportunities)} opportunities")
    
    return {
        'status': 'success',
        'opportunities_queued': len(opportunities),
        'task_group_id': result.id
    }


@shared_task
def cleanup_old_opportunities():
    """
    Archive opportunities older than 1 year.
    """
    cutoff_date = timezone.now() - timedelta(days=365)
    
    old_opportunities = Opportunity.objects.filter(
        posted_date__lt=cutoff_date,
        is_active=True
    )
    
    count = old_opportunities.update(is_active=False)
    
    logger.info(f"Archived {count} old opportunities")
    
    return {
        'status': 'success',
        'archived_count': count
    }