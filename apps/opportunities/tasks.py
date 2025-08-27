"""
Celery tasks for opportunity management.
Handles fetching, processing, and updating opportunities from SAM.gov.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import shared_task, chord, group
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.db import transaction

from .models import Opportunity
from .api_clients.sam_gov import SAMGovClient, SAMGovAPIError
from .api_clients.usaspending_gov import USASpendingClient
from apps.core.models import NAICSCode, Agency
from apps.documents.tasks import fetch_opportunity_documents
from apps.agents.agent_os_integration import agent_os, trigger_workflow

logger = logging.getLogger('blackcoral.opportunities.tasks')


@shared_task(bind=True, max_retries=3)
def process_agent_os_workflow_result(self, workflow_id: str, opportunity_id: int):
    """
    Process the results from an Agent OS workflow for an opportunity.
    This includes AI analysis, compliance checks, and recommendations.
    """
    try:
        # Get workflow status
        workflow_status = agent_os.get_workflow_status(workflow_id)
        
        if workflow_status['status'] != 'completed':
            # Retry if not completed
            logger.info(f"Workflow {workflow_id} not yet completed, retrying...")
            raise self.retry(countdown=60)
        
        # Get the opportunity
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        # Process workflow results
        results = workflow_status.get('results', {})
        
        # Update opportunity with AI insights
        if 'ai_analysis' in results:
            opportunity.metadata['ai_analysis'] = results['ai_analysis']
            opportunity.metadata['ai_confidence_score'] = results.get('confidence_score', 0)
            opportunity.metadata['ai_recommendation'] = results.get('recommendation', 'review')
        
        # Update compliance status
        if 'compliance_check' in results:
            opportunity.metadata['compliance_status'] = results['compliance_check']
            opportunity.metadata['compliance_issues'] = results.get('compliance_issues', [])
        
        # Update decision recommendation
        if 'decision' in results:
            opportunity.metadata['agent_os_decision'] = results['decision']
            opportunity.metadata['decision_factors'] = results.get('decision_factors', [])
        
        # Mark workflow as processed
        opportunity.metadata['agent_os_workflow_processed'] = True
        opportunity.metadata['agent_os_workflow_processed_at'] = timezone.now().isoformat()
        
        opportunity.save(update_fields=['metadata'])
        
        logger.info(f"Successfully processed Agent OS workflow {workflow_id} for opportunity {opportunity_id}")
        
        # Notify team if high-value opportunity
        if results.get('recommendation') == 'high_priority':
            from apps.notifications.services import notification_service
            notification_service.notify_team(
                'high_value_opportunity',
                {
                    'opportunity_id': opportunity_id,
                    'title': opportunity.title,
                    'confidence_score': results.get('confidence_score', 0)
                }
            )
        
        return {
            'status': 'success',
            'workflow_id': workflow_id,
            'opportunity_id': opportunity_id,
            'recommendation': results.get('recommendation')
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error processing Agent OS workflow {workflow_id}: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


def process_opportunity_sync(opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous version of process_opportunity for when Celery is not available.
    """
    # Extract the actual processing logic from the Celery task
    try:
        logger.info(f"Processing opportunity synchronously: {opportunity_data.get('noticeId', 'Unknown')}")
        
        notice_id = opportunity_data.get('noticeId')
        solicitation_number = opportunity_data.get('solicitationNumber')
        
        if not notice_id:
            logger.error("Opportunity missing noticeId")
            return {'status': 'error', 'message': 'Missing noticeId'}
        
        # Use solicitation number if available, otherwise fall back to notice_id
        primary_identifier = solicitation_number if solicitation_number else notice_id
        
        # Get or create agency
        agency = None
        if opportunity_data.get('fullParentPathName'):
            agency_name = opportunity_data['fullParentPathName'].split('.')[-1]
            agency, _ = Agency.objects.get_or_create(
                abbreviation=agency_name[:20],
                defaults={'name': agency_name}
            )
        
        # Parse dates with flexible parsing
        posted_date = None
        if opportunity_data.get('postedDate'):
            posted_date = parse_date_flexible(opportunity_data['postedDate'])
        
        response_date = None
        response_date_str = (opportunity_data.get('responseDeadLine') or 
                           opportunity_data.get('response_date') or
                           opportunity_data.get('responseDate'))
        if response_date_str:
            response_date = parse_date_flexible(response_date_str)
        
        # Extract set aside type with fallback
        set_aside_type = (opportunity_data.get('typeOfSetAsideDescription') or 
                         opportunity_data.get('setAsideType') or 
                         opportunity_data.get('set_aside_type') or 
                         'none')
        
        # Enhance description if available
        description = opportunity_data.get('description', '')
        if opportunity_data.get('descriptionEnhanced'):
            # Use enhanced description if already processed
            description = opportunity_data.get('description', '')
        elif opportunity_data.get('resourceLinks') or opportunity_data.get('additionalInfoLink'):
            # Try to enhance description from URLs if not already done
            try:
                from .api_clients.sam_gov import SAMGovClient
                client = SAMGovClient()
                enhanced_description = client.get_enhanced_opportunity_description(opportunity_data)
                if enhanced_description and len(enhanced_description) > len(description):
                    description = enhanced_description
                    logger.info(f"Enhanced description for opportunity {notice_id} from {len(opportunity_data.get('description', ''))} to {len(description)} characters")
            except Exception as e:
                logger.warning(f"Failed to enhance description for opportunity {notice_id}: {e}")
                description = opportunity_data.get('description', '')
        
        # Prepare opportunity data with robust defaults
        # Ensure place_of_performance is never None
        place_of_performance = opportunity_data.get('placeOfPerformance')
        if place_of_performance is None:
            place_of_performance = {}
        
        # Ensure point_of_contact is never None
        point_of_contact = opportunity_data.get('pointOfContact')
        if point_of_contact is None:
            point_of_contact = {}
        
        opportunity_defaults = {
            'title': opportunity_data.get('title', 'Untitled Opportunity')[:500],
            'description': description,
            'notice_id': notice_id,
            'agency': agency,
            'posted_date': posted_date or timezone.now(),
            'response_date': response_date,
            'source_url': opportunity_data.get('uiLink', '')[:200],
            'source_api': 'sam.gov',
            'raw_data': opportunity_data,
            'opportunity_type': opportunity_data.get('type', '')[:50],
            'set_aside_type': set_aside_type[:100],
            'place_of_performance': place_of_performance,
            'point_of_contact': point_of_contact,
        }
        
        # Create or update opportunity
        with transaction.atomic():
            opportunity, created = Opportunity.objects.update_or_create(
                solicitation_number=primary_identifier,
                defaults=opportunity_defaults
            )
            
            # Add NAICS codes
            naics_codes = opportunity_data.get('naicsCode') or opportunity_data.get('naicsCodes', [])
            if naics_codes:
                if isinstance(naics_codes, str):
                    naics_codes = [naics_codes]
                
                for naics_code in naics_codes:
                    try:
                        naics = NAICSCode.objects.get(code=naics_code)
                        opportunity.naics_codes.add(naics)
                    except NAICSCode.DoesNotExist:
                        logger.warning(f"NAICS code not found: {naics_code}")
                    except Exception as e:
                        logger.warning(f"Error adding NAICS code {naics_code}: {e}")
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} opportunity: {primary_identifier} (Notice ID: {notice_id})")
        
        return {
            'status': 'success',
            'notice_id': notice_id,
            'solicitation_number': primary_identifier,
            'action': action.lower(),
            'created': created
        }
        
    except Exception as e:
        logger.error(f"Error processing opportunity {opportunity_data.get('noticeId', 'Unknown')}: {e}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=3)
def fetch_new_opportunities(self):
    """
    Fetch new opportunities from SAM.gov API.
    Runs hourly during business hours.
    """
    try:
        # Use v3 API for enhanced description support when available
        client = SAMGovClient()
        
        # Fetch opportunities from the last 30 days to capture more opportunities
        posted_from = timezone.now() - timedelta(days=30)
        posted_to = timezone.now()
        
        # Get active NAICS codes we're interested in
        active_naics = list(NAICSCode.objects.filter(
            is_active=True
        ).values_list('code', flat=True))
        
        # If no NAICS codes are set, fetch all opportunities
        if active_naics:
            logger.info(f"Fetching opportunities for {len(active_naics)} NAICS codes")
        else:
            logger.info("No NAICS codes configured - fetching all opportunities")
        
        # Fetch in batches to handle pagination
        all_opportunities = []
        offset = 0
        limit = 100
        
        while True:
            try:
                # Don't pass empty NAICS list to API
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


def parse_date_flexible(date_str) -> datetime:
    """
    Parse date string in various formats and return timezone-aware datetime.
    Handles string dates and existing datetime objects.
    """
    if not date_str:
        return None
    
    # If it's already a datetime object, ensure it's timezone-aware
    if isinstance(date_str, datetime):
        if timezone.is_naive(date_str):
            return timezone.make_aware(date_str)
        return date_str
    
    # Convert to string if it's not already
    date_str = str(date_str).strip()
    if not date_str:
        return None
    
    # Common date formats from SAM.gov API
    date_formats = [
        '%m/%d/%Y',          # 08/14/2025
        '%Y-%m-%d',          # 2025-08-14
        '%m-%d-%Y',          # 08-14-2025
        '%Y/%m/%d',          # 2025/08/14
        '%Y-%m-%dT%H:%M:%S', # 2025-08-14T00:00:00 (ISO format)
        '%Y-%m-%d %H:%M:%S', # 2025-08-14 00:00:00
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            # Convert to timezone-aware datetime
            return timezone.make_aware(parsed_date)
        except ValueError:
            continue
    
    # Try Django's built-in parsers
    try:
        parsed_date = parse_date(date_str) or parse_datetime(date_str)
        if parsed_date:
            if timezone.is_naive(parsed_date):
                return timezone.make_aware(parsed_date)
            return parsed_date
    except ValueError:
        pass
    
    logger.warning(f"Could not parse date: {date_str}")
    return None


@shared_task(bind=True, max_retries=3)
def process_opportunity(self, opportunity_data: Dict[str, Any]):
    """
    Process a single opportunity from SAM.gov.
    Creates or updates the opportunity in the database.
    """
    try:
        notice_id = opportunity_data.get('noticeId')
        solicitation_number = opportunity_data.get('solicitationNumber')
        
        if not notice_id:
            logger.error("Opportunity missing noticeId")
            return
        
        # Use solicitation number if available, otherwise fall back to notice_id
        # This ensures backward compatibility while preferring the correct field
        primary_identifier = solicitation_number if solicitation_number else notice_id
        
        # Get or create agency
        agency = None
        if opportunity_data.get('fullParentPathName'):
            agency_name = opportunity_data['fullParentPathName'].split('.')[-1]
            agency, _ = Agency.objects.get_or_create(
                abbreviation=agency_name[:20],
                defaults={'name': agency_name}
            )
        
        # Parse dates with flexible parsing
        posted_date = None
        if opportunity_data.get('postedDate'):
            posted_date = parse_date_flexible(opportunity_data['postedDate'])
        
        response_date = None
        # Check both possible field names for response date
        response_date_str = (opportunity_data.get('responseDeadLine') or 
                           opportunity_data.get('response_date') or
                           opportunity_data.get('responseDate'))
        if response_date_str:
            response_date = parse_date_flexible(response_date_str)
        
        # Extract set aside type with fallback
        set_aside_type = (opportunity_data.get('typeOfSetAsideDescription') or 
                         opportunity_data.get('setAsideType') or 
                         opportunity_data.get('set_aside_type') or 
                         'none')
        
        # Enhance description if available
        description = opportunity_data.get('description', '')
        if opportunity_data.get('descriptionEnhanced'):
            # Use enhanced description if already processed
            description = opportunity_data.get('description', '')
        elif opportunity_data.get('resourceLinks') or opportunity_data.get('additionalInfoLink'):
            # Try to enhance description from URLs if not already done
            try:
                from .api_clients.sam_gov import SAMGovClient
                client = SAMGovClient()
                enhanced_description = client.get_enhanced_opportunity_description(opportunity_data)
                if enhanced_description and len(enhanced_description) > len(description):
                    description = enhanced_description
                    logger.info(f"Enhanced description for opportunity {notice_id} from {len(opportunity_data.get('description', ''))} to {len(description)} characters")
            except Exception as e:
                logger.warning(f"Failed to enhance description for opportunity {notice_id}: {e}")
                description = opportunity_data.get('description', '')
        
        # Prepare opportunity data with robust defaults
        # Ensure place_of_performance is never None
        place_of_performance = opportunity_data.get('placeOfPerformance')
        if place_of_performance is None:
            place_of_performance = {}
        
        # Ensure point_of_contact is never None
        point_of_contact = opportunity_data.get('pointOfContact')
        if point_of_contact is None:
            point_of_contact = {}
        
        opportunity_defaults = {
            'title': opportunity_data.get('title', 'Untitled Opportunity')[:500],
            'description': description,
            'notice_id': notice_id,  # Store the SAM.gov notice ID
            'agency': agency,
            'posted_date': posted_date or timezone.now(),
            'response_date': response_date,
            'source_url': opportunity_data.get('uiLink', '')[:200],  # URL field limit
            'source_api': 'sam.gov',
            'raw_data': opportunity_data,  # Store full response
            'opportunity_type': opportunity_data.get('type', '')[:50],  # Field limit
            'set_aside_type': set_aside_type[:100],  # Ensure field length limit
            'place_of_performance': place_of_performance,
            'point_of_contact': point_of_contact,
        }
        
        # Create or update opportunity
        with transaction.atomic():
            opportunity, created = Opportunity.objects.update_or_create(
                solicitation_number=primary_identifier,
                defaults=opportunity_defaults
            )
            
            # Add NAICS codes - handle both single code and multiple codes
            naics_codes = opportunity_data.get('naicsCode') or opportunity_data.get('naicsCodes', [])
            if naics_codes:
                # Handle both string and list formats
                if isinstance(naics_codes, str):
                    naics_codes = [naics_codes]
                
                for naics_code in naics_codes:
                    try:
                        naics = NAICSCode.objects.get(code=naics_code)
                        opportunity.naics_codes.add(naics)
                    except NAICSCode.DoesNotExist:
                        logger.warning(f"NAICS code not found: {naics_code}")
                    except Exception as e:
                        logger.warning(f"Error adding NAICS code {naics_code}: {e}")
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} opportunity: {primary_identifier} (Notice ID: {notice_id})")
        
        # Fetch documents if new opportunity
        if created:
            try:
                fetch_opportunity_documents.delay(opportunity.id)
            except Exception as e:
                logger.warning(f"Could not queue document fetch for opportunity {opportunity.id}: {e}")
            
            # Trigger Agent OS opportunity processing workflow
            try:
                workflow_result = trigger_workflow('opportunity-intake', {
                    'opportunity_id': opportunity.id,
                    'notice_id': opportunity.notice_id,
                    'naics_codes': [n.code for n in opportunity.naics_codes.all()],
                    'agency': agency.name if agency else None,
                    'title': opportunity.title,
                    'description': opportunity.description[:1000],  # First 1000 chars
                    'solicitation_number': opportunity.solicitation_number,
                    'set_aside_type': opportunity.set_aside_type,
                    'response_date': opportunity.response_date.isoformat() if opportunity.response_date else None,
                    'user': 'system',
                    'stage': 'discovery'
                })
                logger.info(f"Agent OS workflow triggered for opportunity {opportunity.id}: {workflow_result['workflow_id']}")
                
                # Store workflow ID on opportunity
                opportunity.metadata['agent_os_workflow_id'] = workflow_result['workflow_id']
                opportunity.save(update_fields=['metadata'])
                
            except Exception as e:
                logger.error(f"Failed to trigger Agent OS workflow for opportunity {opportunity.id}: {e}")
        
        return {
            'status': 'success',
            'notice_id': notice_id,
            'solicitation_number': primary_identifier,
            'action': action.lower(),
            'created': created
        }
        
    except Exception as e:
        logger.error(f"Error processing opportunity {opportunity_data.get('noticeId', 'Unknown')}: {e}")
        # Only retry on certain types of errors
        if "duplicate key" in str(e).lower():
            # Don't retry on duplicate key errors
            return {
                'status': 'error',
                'notice_id': opportunity_data.get('noticeId', 'Unknown'),
                'error': 'Duplicate opportunity'
            }
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def fetch_opportunity_details(self, opportunity_id: int):
    """
    Fetch detailed information for a specific opportunity.
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        # Use v3 API for enhanced description support
        client = SAMGovClient()
        
        # Fetch latest details using the notice_id (SAM.gov expects notice ID, not solicitation number)
        notice_id = opportunity.notice_id or opportunity.solicitation_number  # Fallback for legacy data
        details = client.get_opportunity_details(notice_id, fetch_enhanced_description=True)
        
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


@shared_task(bind=True, max_retries=3)
def enhance_opportunity_description(self, opportunity_id: int):
    """
    Enhance description content for a specific opportunity by fetching from URLs.
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        # Skip if description is already substantial (> 500 chars)
        if len(opportunity.description) > 500:
            logger.info(f"Opportunity {opportunity_id} already has substantial description, skipping")
            return {
                'status': 'skipped',
                'opportunity_id': opportunity_id,
                'reason': 'description_already_substantial'
            }
        
        # Use enhanced SAM.gov client
        client = SAMGovClient()
        
        # Get enhanced description from the raw_data
        if opportunity.raw_data:
            try:
                enhanced_description = client.get_enhanced_opportunity_description(opportunity.raw_data)
                
                if enhanced_description and len(enhanced_description) > len(opportunity.description):
                    original_length = len(opportunity.description)
                    opportunity.description = enhanced_description
                    opportunity.save()
                    
                    logger.info(f"Enhanced description for opportunity {opportunity_id} from {original_length} to {len(enhanced_description)} characters")
                    
                    return {
                        'status': 'success',
                        'opportunity_id': opportunity_id,
                        'original_length': original_length,
                        'enhanced_length': len(enhanced_description)
                    }
                else:
                    return {
                        'status': 'no_enhancement',
                        'opportunity_id': opportunity_id,
                        'reason': 'no_additional_content_found'
                    }
                    
            except Exception as e:
                logger.warning(f"Failed to enhance description from raw_data for opportunity {opportunity_id}: {e}")
                
                # Try fetching fresh details as fallback
                if opportunity.notice_id:
                    details = client.get_opportunity_details(opportunity.notice_id, fetch_enhanced_description=True)
                    
                    enhanced_description = details.get('description', '')
                    if enhanced_description and len(enhanced_description) > len(opportunity.description):
                        original_length = len(opportunity.description)
                        opportunity.description = enhanced_description
                        opportunity.raw_data = details  # Update with fresh data
                        opportunity.save()
                        
                        logger.info(f"Enhanced description via fresh fetch for opportunity {opportunity_id} from {original_length} to {len(enhanced_description)} characters")
                        
                        return {
                            'status': 'success',
                            'opportunity_id': opportunity_id,
                            'original_length': original_length,
                            'enhanced_length': len(enhanced_description),
                            'method': 'fresh_fetch'
                        }
        
        return {
            'status': 'no_enhancement',
            'opportunity_id': opportunity_id,
            'reason': 'no_raw_data_or_notice_id'
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found for description enhancement")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error enhancing description for opportunity {opportunity_id}: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def bulk_enhance_opportunity_descriptions(limit: int = 50):
    """
    Enhance descriptions for multiple opportunities that have short or generic descriptions.
    """
    # Find opportunities with short descriptions that might benefit from enhancement
    opportunities = Opportunity.objects.filter(
        is_active=True,
        raw_data__isnull=False
    ).extra(
        where=["LENGTH(description) < 500 OR description ILIKE '%see attachment%' OR description ILIKE '%refer to%'"]
    ).order_by('-posted_date')[:limit]
    
    if not opportunities:
        return {
            'status': 'success',
            'message': 'No opportunities need description enhancement',
            'processed': 0
        }
    
    # Create group of enhancement tasks
    enhancement_tasks = group([
        enhance_opportunity_description.s(opp.id) 
        for opp in opportunities
    ])
    
    # Execute tasks
    result = enhancement_tasks.apply_async()
    
    logger.info(f"Started description enhancement for {len(opportunities)} opportunities")
    
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