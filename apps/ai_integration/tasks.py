"""
AI Integration Celery Tasks for opportunity analysis and content generation
"""

import logging
from typing import Dict, Any
from celery import shared_task, group
from django.utils import timezone

from .services import OpportunityAnalysisService, ComplianceService, ContentGenerationService
from .ai_providers import AIProvider
from apps.opportunities.models import Opportunity

logger = logging.getLogger('blackcoral.ai_integration.tasks')


@shared_task(bind=True, max_retries=3)
def analyze_opportunity_with_ai(self, opportunity_id: int, provider: str = None):
    """
    Perform comprehensive AI analysis of an opportunity
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        # Convert provider string to enum if provided
        ai_provider = None
        if provider:
            try:
                ai_provider = AIProvider(provider)
            except ValueError:
                logger.warning(f"Invalid AI provider: {provider}, using default")
        
        # Prepare opportunity data
        opportunity_data = {
            'title': opportunity.title,
            'solicitation_number': opportunity.solicitation_number,
            'agency_name': opportunity.agency.name if opportunity.agency else None,
            'description': opportunity.description,
            'posted_date': opportunity.posted_date.isoformat() if opportunity.posted_date else None,
            'response_date': opportunity.response_date.isoformat() if opportunity.response_date else None,
            'naics_codes': list(opportunity.naics_codes.values_list('code', flat=True)),
            'set_aside_type': opportunity.set_aside_type,
            'opportunity_type': opportunity.opportunity_type,
            'place_of_performance': opportunity.place_of_performance,
            'point_of_contact': opportunity.point_of_contact
        }
        
        # Get USASpending data if available
        usaspending_data = opportunity.usaspending_data if opportunity.usaspending_analyzed else None
        
        # Perform AI analysis
        analysis_service = OpportunityAnalysisService(preferred_provider=ai_provider)
        analysis = analysis_service.analyze_opportunity(opportunity_data, usaspending_data)
        
        # Store analysis results
        ai_analysis_data = {
            'executive_summary': analysis.executive_summary,
            'technical_requirements': analysis.technical_requirements,
            'business_opportunity': analysis.business_opportunity,
            'risk_assessment': analysis.risk_assessment,
            'compliance_notes': analysis.compliance_notes,
            'competitive_landscape': analysis.competitive_landscape,
            'recommendation': analysis.recommendation,
            'confidence_score': analysis.confidence_score,
            'keywords': analysis.keywords,
            'analyzed_at': timezone.now().isoformat(),
            'provider_used': ai_provider.value if ai_provider else 'auto'
        }
        
        # Update opportunity with AI analysis
        opportunity.ai_analysis_data = ai_analysis_data
        opportunity.ai_analysis_complete = True
        opportunity.save()
        
        logger.info(f"AI analysis completed for opportunity {opportunity_id}")
        
        return {
            'status': 'success',
            'opportunity_id': opportunity_id,
            'confidence_score': analysis.confidence_score,
            'recommendation': analysis.recommendation,
            'provider_used': ai_analysis_data['provider_used']
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found for AI analysis")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error in AI analysis for opportunity {opportunity_id}: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2)
def check_opportunity_compliance(self, opportunity_id: int, provider: str = None):
    """
    Perform AI-powered compliance checking for an opportunity
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        ai_provider = None
        if provider:
            try:
                ai_provider = AIProvider(provider)
            except ValueError:
                logger.warning(f"Invalid AI provider: {provider}, using default")
        
        # Prepare opportunity data
        opportunity_data = {
            'solicitation_number': opportunity.solicitation_number,
            'agency_name': opportunity.agency.name if opportunity.agency else None,
            'description': opportunity.description,
            'set_aside_type': opportunity.set_aside_type,
            'opportunity_type': opportunity.opportunity_type
        }
        
        # Perform compliance check
        compliance_service = ComplianceService(preferred_provider=ai_provider)
        compliance_check = compliance_service.check_compliance(opportunity_data)
        
        # Store compliance results
        compliance_data = {
            'overall_status': compliance_check.overall_status,
            'issues': compliance_check.issues,
            'requirements_met': compliance_check.requirements_met,
            'requirements_missing': compliance_check.requirements_missing,
            'recommendations': compliance_check.recommendations,
            'confidence_score': compliance_check.confidence_score,
            'checked_at': timezone.now().isoformat(),
            'provider_used': ai_provider.value if ai_provider else 'auto'
        }
        
        # Update opportunity compliance data
        opportunity.compliance_data = compliance_data
        opportunity.compliance_checked = True
        opportunity.save()
        
        logger.info(f"Compliance check completed for opportunity {opportunity_id}")
        
        return {
            'status': 'success',
            'opportunity_id': opportunity_id,
            'compliance_status': compliance_check.overall_status,
            'confidence_score': compliance_check.confidence_score
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found for compliance check")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error in compliance check for opportunity {opportunity_id}: {e}")
        raise self.retry(exc=e, countdown=180)


@shared_task(bind=True, max_retries=2)
def generate_opportunity_content(self, opportunity_id: int, content_type: str, provider: str = None):
    """
    Generate AI-powered content for opportunities (outlines, summaries, etc.)
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        ai_provider = None
        if provider:
            try:
                ai_provider = AIProvider(provider)
            except ValueError:
                logger.warning(f"Invalid AI provider: {provider}, using default")
        
        # Check if AI analysis exists
        if not opportunity.ai_analysis_complete:
            logger.warning(f"Triggering AI analysis first for opportunity {opportunity_id}")
            analyze_opportunity_with_ai.delay(opportunity_id, provider)
            return {'status': 'pending', 'message': 'AI analysis required first'}
        
        # Get analysis data
        from .services import OpportunityAnalysis
        analysis_data = opportunity.ai_analysis_data
        analysis = OpportunityAnalysis(
            executive_summary=analysis_data.get('executive_summary', ''),
            technical_requirements=analysis_data.get('technical_requirements', []),
            business_opportunity=analysis_data.get('business_opportunity', ''),
            risk_assessment=analysis_data.get('risk_assessment', ''),
            compliance_notes=analysis_data.get('compliance_notes', ''),
            competitive_landscape=analysis_data.get('competitive_landscape', ''),
            recommendation=analysis_data.get('recommendation', ''),
            confidence_score=analysis_data.get('confidence_score', 0.5),
            keywords=analysis_data.get('keywords', [])
        )
        
        # Prepare opportunity data
        opportunity_data = {
            'title': opportunity.title,
            'agency_name': opportunity.agency.name if opportunity.agency else None,
            'description': opportunity.description
        }
        
        # Generate content based on type
        content_service = ContentGenerationService(preferred_provider=ai_provider)
        
        if content_type == 'proposal_outline':
            content = content_service.generate_proposal_outline(opportunity_data, analysis)
        elif content_type == 'executive_summary':
            content = content_service.generate_executive_summary(opportunity_data, analysis)
        else:
            raise ValueError(f"Unknown content type: {content_type}")
        
        # Store generated content
        if not opportunity.generated_content:
            opportunity.generated_content = {}
        
        opportunity.generated_content[content_type] = {
            'content': content,
            'generated_at': timezone.now().isoformat(),
            'provider_used': ai_provider.value if ai_provider else 'auto'
        }
        opportunity.save()
        
        logger.info(f"Content generation ({content_type}) completed for opportunity {opportunity_id}")
        
        return {
            'status': 'success',
            'opportunity_id': opportunity_id,
            'content_type': content_type,
            'content_length': len(content)
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found for content generation")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error in content generation for opportunity {opportunity_id}: {e}")
        raise self.retry(exc=e, countdown=180)


@shared_task
def bulk_analyze_opportunities(opportunity_ids: list, provider: str = None):
    """
    Perform bulk AI analysis for multiple opportunities
    """
    if not opportunity_ids:
        return {
            'status': 'success',
            'message': 'No opportunities to analyze',
            'processed': 0
        }
    
    # Create group of analysis tasks
    analysis_tasks = group([
        analyze_opportunity_with_ai.s(opp_id, provider)
        for opp_id in opportunity_ids
    ])
    
    # Execute tasks
    result = analysis_tasks.apply_async()
    
    logger.info(f"Started bulk AI analysis for {len(opportunity_ids)} opportunities")
    
    return {
        'status': 'success',
        'opportunities_queued': len(opportunity_ids),
        'task_group_id': result.id,
        'provider': provider or 'auto'
    }


@shared_task
def auto_analyze_new_opportunities(hours_back: int = 24):
    """
    Automatically analyze opportunities posted in the last N hours
    """
    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(hours=hours_back)
    
    new_opportunities = Opportunity.objects.filter(
        posted_date__gte=cutoff_time,
        ai_analysis_complete=False,
        is_active=True
    ).values_list('id', flat=True)
    
    if not new_opportunities:
        return {
            'status': 'success',
            'message': f'No new opportunities in last {hours_back} hours',
            'processed': 0
        }
    
    # Trigger bulk analysis
    return bulk_analyze_opportunities(list(new_opportunities))


@shared_task
def test_ai_providers():
    """Test all configured AI providers"""
    from .ai_providers import ai_manager
    from .services import OpportunityAnalysisService
    
    test_data = {
        'title': 'Test Engineering Services Contract',
        'solicitation_number': 'TEST-2024-001',
        'agency_name': 'Department of Defense',
        'description': 'Test opportunity for AI provider validation',
        'naics_codes': ['541330']
    }
    
    results = {}
    available_providers = ai_manager.get_available_providers()
    
    for provider in available_providers:
        try:
            service = OpportunityAnalysisService(preferred_provider=provider)
            analysis = service.analyze_opportunity(test_data)
            
            results[provider.value] = {
                'status': 'success',
                'confidence_score': analysis.confidence_score,
                'summary_length': len(analysis.executive_summary)
            }
            
        except Exception as e:
            results[provider.value] = {
                'status': 'error',
                'error': str(e)
            }
    
    return {
        'status': 'completed',
        'providers_tested': len(available_providers),
        'results': results
    }


@shared_task(bind=True, max_retries=2)
def evaluate_bid_decision(self, opportunity_id: int, user_id: int = None):
    """
    Generate bid/no-bid decision for an opportunity using AI decision engine
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        # Check if AI analysis is complete
        if not opportunity.ai_analysis_complete:
            logger.warning(f"Opportunity {opportunity_id} needs AI analysis before decision evaluation")
            return {
                'status': 'pending',
                'message': 'AI analysis required before decision evaluation'
            }
        
        # Import here to avoid circular imports
        from .decision_engine import evaluate_opportunity_decision
        from .models import BidDecisionRecord
        from django.contrib.auth import get_user_model
        
        # Generate decision
        decision = evaluate_opportunity_decision(opportunity)
        
        if not decision:
            raise Exception("Failed to generate decision")
        
        # Get user if provided
        User = get_user_model()
        decided_by = None
        if user_id:
            try:
                decided_by = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        # Store decision in database
        bid_decision, created = BidDecisionRecord.objects.update_or_create(
            opportunity=opportunity,
            defaults={
                'recommendation': decision.recommendation,
                'overall_score': decision.overall_score,
                'confidence_score': decision.confidence_score,
                'strategic_alignment': decision.factors.strategic_alignment,
                'capability_match': decision.factors.capability_match,
                'market_position': decision.factors.market_position,
                'estimated_value': decision.factors.estimated_value,
                'profit_potential': decision.factors.profit_potential,
                'resource_requirements': decision.factors.resource_requirements,
                'technical_risk': decision.factors.technical_risk,
                'schedule_risk': decision.factors.schedule_risk,
                'competitive_risk': decision.factors.competitive_risk,
                'rationale': decision.rationale,
                'key_strengths': decision.key_strengths,
                'key_concerns': decision.key_concerns,
                'action_items': decision.action_items,
                'estimated_bid_cost': decision.estimated_bid_cost,
                'win_probability': decision.win_probability,
                'decided_by': decided_by
            }
        )
        
        logger.info(f"Bid decision completed for opportunity {opportunity_id}: {decision.recommendation}")
        
        return {
            'status': 'success',
            'opportunity_id': opportunity_id,
            'recommendation': decision.recommendation,
            'overall_score': decision.overall_score,
            'win_probability': decision.win_probability,
            'estimated_bid_cost': float(decision.estimated_bid_cost) if decision.estimated_bid_cost else None,
            'decision_record_id': bid_decision.id,
            'created': created
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found for decision evaluation")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error in bid decision evaluation for opportunity {opportunity_id}: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def bulk_evaluate_decisions(opportunity_ids: list, user_id: int = None):
    """
    Evaluate bid/no-bid decisions for multiple opportunities
    """
    if not opportunity_ids:
        return {
            'status': 'success',
            'message': 'No opportunities to evaluate',
            'processed': 0
        }
    
    # Create group of decision evaluation tasks
    decision_tasks = group([
        evaluate_bid_decision.s(opp_id, user_id)
        for opp_id in opportunity_ids
    ])
    
    # Execute tasks
    result = decision_tasks.apply_async()
    
    logger.info(f"Started bulk decision evaluation for {len(opportunity_ids)} opportunities")
    
    return {
        'status': 'success',
        'opportunities_queued': len(opportunity_ids),
        'task_group_id': result.id,
        'user_id': user_id
    }


@shared_task
def auto_evaluate_analyzed_opportunities():
    """
    Automatically evaluate decisions for opportunities that have AI analysis but no decision
    """
    from .models import BidDecisionRecord
    
    # Find opportunities with AI analysis but no decision
    analyzed_without_decision = Opportunity.objects.filter(
        ai_analysis_complete=True,
        is_active=True
    ).exclude(
        id__in=BidDecisionRecord.objects.values_list('opportunity_id', flat=True)
    ).values_list('id', flat=True)
    
    if not analyzed_without_decision:
        return {
            'status': 'success',
            'message': 'No opportunities need decision evaluation',
            'processed': 0
        }
    
    # Trigger bulk evaluation
    return bulk_evaluate_decisions(list(analyzed_without_decision))


@shared_task
def update_decision_metrics():
    """
    Update decision accuracy metrics by comparing predictions to actual outcomes
    """
    from .models import BidDecisionRecord
    from django.db.models import Avg, Count, Q
    
    # Get decisions with actual outcomes
    decisions_with_outcomes = BidDecisionRecord.objects.filter(
        contract_awarded=True,
        won_contract__isnull=False
    )
    
    if not decisions_with_outcomes.exists():
        return {
            'status': 'success',
            'message': 'No decisions with outcomes to analyze',
            'metrics': {}
        }
    
    # Calculate accuracy metrics
    total_decisions = decisions_with_outcomes.count()
    
    # Win rate by recommendation
    bid_recommendations = decisions_with_outcomes.filter(recommendation='BID')
    bid_wins = bid_recommendations.filter(won_contract=True).count()
    bid_total = bid_recommendations.count()
    bid_accuracy = (bid_wins / bid_total * 100) if bid_total > 0 else 0
    
    # Average score by outcome
    winners_avg_score = decisions_with_outcomes.filter(won_contract=True).aggregate(
        Avg('overall_score')
    )['overall_score__avg'] or 0
    
    losers_avg_score = decisions_with_outcomes.filter(won_contract=False).aggregate(
        Avg('overall_score')
    )['overall_score__avg'] or 0
    
    # Win probability accuracy
    win_prob_decisions = decisions_with_outcomes.filter(win_probability__isnull=False)
    if win_prob_decisions.exists():
        # Calculate correlation between predicted and actual win rates
        predicted_wins = sum(d.win_probability for d in win_prob_decisions)
        actual_wins = win_prob_decisions.filter(won_contract=True).count()
        win_prob_accuracy = abs(predicted_wins - actual_wins) / len(win_prob_decisions)
    else:
        win_prob_accuracy = 0
    
    metrics = {
        'total_decisions_analyzed': total_decisions,
        'bid_recommendation_accuracy': round(bid_accuracy, 1),
        'winners_avg_score': round(winners_avg_score, 1),
        'losers_avg_score': round(losers_avg_score, 1),
        'win_probability_accuracy': round((1 - win_prob_accuracy) * 100, 1),
        'analyzed_at': timezone.now().isoformat()
    }
    
    logger.info(f"Decision metrics updated: {metrics}")
    
    return {
        'status': 'success',
        'metrics': metrics
    }