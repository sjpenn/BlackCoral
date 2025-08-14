"""
BLACK CORAL Analytics Engine
Advanced reporting and insights for bid/no-bid decisions and opportunity analysis
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Q, Avg, Count, Sum, Max, Min
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from .models import BidDecisionRecord, AITask
from apps.opportunities.models import Opportunity
from apps.core.models import Agency, NAICSCode

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Advanced analytics for BLACK CORAL decision intelligence"""
    
    def __init__(self, date_range_days: int = 90):
        self.date_range = timezone.now() - timedelta(days=date_range_days)
        self.logger = logging.getLogger(f"{__name__}.AnalyticsEngine")
    
    def get_decision_summary(self) -> Dict[str, Any]:
        """Get overall decision summary and metrics"""
        
        # Get base querysets
        all_decisions = BidDecisionRecord.objects.filter(decision_date__gte=self.date_range)
        total_decisions = all_decisions.count()
        
        if total_decisions == 0:
            return self._empty_summary()
        
        # Decision distribution
        decision_distribution = {
            'BID': all_decisions.filter(recommendation='BID').count(),
            'NO_BID': all_decisions.filter(recommendation='NO_BID').count(),
            'WATCH': all_decisions.filter(recommendation='WATCH').count()
        }
        
        # Score analysis
        score_stats = all_decisions.aggregate(
            avg_score=Avg('overall_score'),
            max_score=Max('overall_score'),
            min_score=Min('overall_score')
        )
        
        # Win probability analysis
        win_prob_stats = all_decisions.filter(
            win_probability__isnull=False
        ).aggregate(
            avg_win_prob=Avg('win_probability'),
            high_prob_count=Count('id', filter=Q(win_probability__gte=0.7))
        )
        
        # Financial analysis
        financial_stats = all_decisions.aggregate(
            total_estimated_value=Sum('estimated_bid_cost'),
            avg_bid_cost=Avg('estimated_bid_cost')
        )
        
        # Risk analysis
        risk_stats = all_decisions.aggregate(
            avg_technical_risk=Avg('technical_risk'),
            avg_schedule_risk=Avg('schedule_risk'),
            avg_competitive_risk=Avg('competitive_risk')
        )
        
        # Performance metrics (for decisions with outcomes)
        performance = self._calculate_performance_metrics(all_decisions)
        
        return {
            'period': {
                'start_date': self.date_range.date(),
                'end_date': timezone.now().date(),
                'total_decisions': total_decisions
            },
            'distribution': decision_distribution,
            'scores': {
                'average': round(score_stats['avg_score'] or 0, 1),
                'highest': round(score_stats['max_score'] or 0, 1),
                'lowest': round(score_stats['min_score'] or 0, 1),
                'excellent_count': all_decisions.filter(overall_score__gte=80).count(),
                'good_count': all_decisions.filter(overall_score__gte=70, overall_score__lt=80).count(),
                'fair_count': all_decisions.filter(overall_score__gte=50, overall_score__lt=70).count(),
                'poor_count': all_decisions.filter(overall_score__lt=50).count()
            },
            'win_probability': {
                'average': round((win_prob_stats['avg_win_prob'] or 0) * 100, 1),
                'high_probability_count': win_prob_stats['high_prob_count'] or 0
            },
            'financial': {
                'total_estimated_bid_cost': float(financial_stats['total_estimated_value'] or 0),
                'average_bid_cost': float(financial_stats['avg_bid_cost'] or 0)
            },
            'risk_profile': {
                'technical_risk': round((1 - (risk_stats['avg_technical_risk'] or 0.5)) * 100, 1),
                'schedule_risk': round((1 - (risk_stats['avg_schedule_risk'] or 0.5)) * 100, 1),
                'competitive_risk': round((1 - (risk_stats['avg_competitive_risk'] or 0.5)) * 100, 1)
            },
            'performance': performance
        }
    
    def get_agency_analysis(self) -> List[Dict[str, Any]]:
        """Analyze decisions by agency"""
        
        agency_decisions = BidDecisionRecord.objects.filter(
            decision_date__gte=self.date_range,
            opportunity__agency__isnull=False
        ).values(
            'opportunity__agency__name',
            'opportunity__agency__abbreviation'
        ).annotate(
            total_decisions=Count('id'),
            bid_count=Count('id', filter=Q(recommendation='BID')),
            avg_score=Avg('overall_score'),
            avg_win_prob=Avg('win_probability'),
            total_bid_cost=Sum('estimated_bid_cost'),
            wins=Count('id', filter=Q(won_contract=True))
        ).order_by('-total_decisions')
        
        agency_analysis = []
        for agency in agency_decisions:
            win_rate = 0
            if agency['wins'] and agency['bid_count']:
                win_rate = (agency['wins'] / agency['bid_count']) * 100
            
            agency_analysis.append({
                'name': agency['opportunity__agency__name'],
                'abbreviation': agency['opportunity__agency__abbreviation'],
                'total_decisions': agency['total_decisions'],
                'bid_count': agency['bid_count'],
                'bid_rate': round((agency['bid_count'] / agency['total_decisions']) * 100, 1),
                'average_score': round(agency['avg_score'] or 0, 1),
                'average_win_probability': round((agency['avg_win_prob'] or 0) * 100, 1),
                'total_estimated_costs': float(agency['total_bid_cost'] or 0),
                'win_rate': round(win_rate, 1),
                'wins': agency['wins']
            })
        
        return agency_analysis[:10]  # Top 10 agencies
    
    def get_naics_analysis(self) -> List[Dict[str, Any]]:
        """Analyze decisions by NAICS codes"""
        
        # Get opportunities with decisions and NAICS codes
        naics_analysis = []
        
        naics_codes = NAICSCode.objects.filter(
            opportunity__bid_decision__decision_date__gte=self.date_range
        ).annotate(
            total_decisions=Count('opportunity__bid_decision'),
            bid_count=Count('opportunity__bid_decision', filter=Q(opportunity__bid_decision__recommendation='BID')),
            avg_score=Avg('opportunity__bid_decision__overall_score'),
            avg_win_prob=Avg('opportunity__bid_decision__win_probability'),
            wins=Count('opportunity__bid_decision', filter=Q(opportunity__bid_decision__won_contract=True))
        ).order_by('-total_decisions')
        
        for naics in naics_codes[:10]:  # Top 10 NAICS
            win_rate = 0
            if naics.wins and naics.bid_count:
                win_rate = (naics.wins / naics.bid_count) * 100
            
            naics_analysis.append({
                'code': naics.code,
                'title': naics.title,
                'total_decisions': naics.total_decisions,
                'bid_count': naics.bid_count,
                'bid_rate': round((naics.bid_count / naics.total_decisions) * 100, 1) if naics.total_decisions else 0,
                'average_score': round(naics.avg_score or 0, 1),
                'average_win_probability': round((naics.avg_win_prob or 0) * 100, 1),
                'win_rate': round(win_rate, 1),
                'wins': naics.wins
            })
        
        return naics_analysis
    
    def get_trend_analysis(self) -> Dict[str, Any]:
        """Analyze trends over time"""
        
        # Monthly trends
        monthly_trends = BidDecisionRecord.objects.filter(
            decision_date__gte=self.date_range
        ).annotate(
            month=TruncMonth('decision_date')
        ).values('month').annotate(
            total_decisions=Count('id'),
            bid_decisions=Count('id', filter=Q(recommendation='BID')),
            avg_score=Avg('overall_score'),
            avg_win_prob=Avg('win_probability')
        ).order_by('month')
        
        # Weekly trends (last 12 weeks)
        twelve_weeks_ago = timezone.now() - timedelta(weeks=12)
        weekly_trends = BidDecisionRecord.objects.filter(
            decision_date__gte=twelve_weeks_ago
        ).annotate(
            week=TruncWeek('decision_date')
        ).values('week').annotate(
            total_decisions=Count('id'),
            bid_decisions=Count('id', filter=Q(recommendation='BID')),
            avg_score=Avg('overall_score')
        ).order_by('week')
        
        return {
            'monthly': [
                {
                    'month': trend['month'].strftime('%Y-%m'),
                    'total_decisions': trend['total_decisions'],
                    'bid_decisions': trend['bid_decisions'],
                    'bid_rate': round((trend['bid_decisions'] / trend['total_decisions']) * 100, 1),
                    'average_score': round(trend['avg_score'] or 0, 1),
                    'average_win_probability': round((trend['avg_win_prob'] or 0) * 100, 1)
                }
                for trend in monthly_trends
            ],
            'weekly': [
                {
                    'week': trend['week'].strftime('%Y-%m-%d'),
                    'total_decisions': trend['total_decisions'],
                    'bid_decisions': trend['bid_decisions'],
                    'average_score': round(trend['avg_score'] or 0, 1)
                }
                for trend in weekly_trends
            ]
        }
    
    def get_ai_performance_metrics(self) -> Dict[str, Any]:
        """Analyze AI model performance and accuracy"""
        
        # AI task performance
        ai_tasks = AITask.objects.filter(
            created_at__gte=self.date_range,
            status='completed'
        )
        
        task_performance = ai_tasks.values('task_type', 'ai_provider').annotate(
            count=Count('id'),
            avg_processing_time=Avg('processing_time'),
            avg_confidence=Avg('confidence_score'),
            avg_tokens=Avg('tokens_used')
        )
        
        # Decision accuracy (where outcomes are known)
        decisions_with_outcomes = BidDecisionRecord.objects.filter(
            decision_date__gte=self.date_range,
            contract_awarded=True,
            won_contract__isnull=False
        )
        
        accuracy_metrics = {}
        if decisions_with_outcomes.exists():
            # Recommendation accuracy
            bid_recommendations = decisions_with_outcomes.filter(recommendation='BID')
            bid_wins = bid_recommendations.filter(won_contract=True).count()
            bid_accuracy = (bid_wins / bid_recommendations.count() * 100) if bid_recommendations.count() > 0 else 0
            
            # Score correlation with wins
            winners_avg_score = decisions_with_outcomes.filter(won_contract=True).aggregate(
                Avg('overall_score')
            )['overall_score__avg'] or 0
            
            losers_avg_score = decisions_with_outcomes.filter(won_contract=False).aggregate(
                Avg('overall_score')
            )['overall_score__avg'] or 0
            
            accuracy_metrics = {
                'bid_recommendation_accuracy': round(bid_accuracy, 1),
                'winners_average_score': round(winners_avg_score, 1),
                'losers_average_score': round(losers_avg_score, 1),
                'score_differentiation': round(winners_avg_score - losers_avg_score, 1)
            }
        
        return {
            'task_performance': [
                {
                    'task_type': task['task_type'],
                    'provider': task['ai_provider'],
                    'count': task['count'],
                    'avg_processing_time': round(task['avg_processing_time'] or 0, 2),
                    'avg_confidence': round(task['avg_confidence'] or 0, 2),
                    'avg_tokens': round(task['avg_tokens'] or 0)
                }
                for task in task_performance
            ],
            'accuracy_metrics': accuracy_metrics,
            'total_completed_tasks': ai_tasks.count()
        }
    
    def get_competitive_intelligence(self) -> Dict[str, Any]:
        """Analyze competitive landscape insights"""
        
        # Analyze win rates by competitive risk level
        competitive_analysis = BidDecisionRecord.objects.filter(
            decision_date__gte=self.date_range,
            contract_awarded=True,
            won_contract__isnull=False
        ).extra(
            select={
                'competition_level': """
                    CASE 
                        WHEN competitive_risk >= 0.8 THEN 'Low Competition'
                        WHEN competitive_risk >= 0.6 THEN 'Medium Competition'
                        ELSE 'High Competition'
                    END
                """
            }
        ).values('competition_level').annotate(
            total_bids=Count('id'),
            wins=Count('id', filter=Q(won_contract=True)),
            avg_score=Avg('overall_score'),
            avg_bid_cost=Avg('estimated_bid_cost')
        )
        
        # Market opportunity analysis
        market_opportunities = BidDecisionRecord.objects.filter(
            decision_date__gte=self.date_range,
            recommendation='BID'
        ).aggregate(
            total_market_value=Sum('estimated_bid_cost'),
            high_value_opportunities=Count('id', filter=Q(estimated_bid_cost__gte=100000)),
            strategic_opportunities=Count('id', filter=Q(strategic_alignment__gte=0.8))
        )
        
        return {
            'competitive_landscape': [
                {
                    'competition_level': comp['competition_level'],
                    'total_bids': comp['total_bids'],
                    'wins': comp['wins'],
                    'win_rate': round((comp['wins'] / comp['total_bids']) * 100, 1) if comp['total_bids'] > 0 else 0,
                    'average_score': round(comp['avg_score'] or 0, 1),
                    'average_bid_cost': float(comp['avg_bid_cost'] or 0)
                }
                for comp in competitive_analysis
            ],
            'market_insights': {
                'total_addressable_market': float(market_opportunities['total_market_value'] or 0),
                'high_value_opportunities': market_opportunities['high_value_opportunities'],
                'strategic_opportunities': market_opportunities['strategic_opportunities']
            }
        }
    
    def _calculate_performance_metrics(self, decisions_queryset) -> Dict[str, Any]:
        """Calculate performance metrics for decisions with known outcomes"""
        
        decisions_with_outcomes = decisions_queryset.filter(
            contract_awarded=True,
            won_contract__isnull=False
        )
        
        if not decisions_with_outcomes.exists():
            return {
                'has_outcomes': False,
                'message': 'No decisions with known outcomes yet'
            }
        
        total_with_outcomes = decisions_with_outcomes.count()
        wins = decisions_with_outcomes.filter(won_contract=True).count()
        
        # Bid recommendations that were actually pursued
        bid_recommendations = decisions_with_outcomes.filter(recommendation='BID')
        bid_wins = bid_recommendations.filter(won_contract=True).count()
        
        return {
            'has_outcomes': True,
            'total_decisions_with_outcomes': total_with_outcomes,
            'total_wins': wins,
            'overall_win_rate': round((wins / total_with_outcomes) * 100, 1),
            'bid_recommendations': bid_recommendations.count(),
            'bid_wins': bid_wins,
            'bid_win_rate': round((bid_wins / bid_recommendations.count()) * 100, 1) if bid_recommendations.count() > 0 else 0
        }
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary when no data available"""
        return {
            'period': {
                'start_date': self.date_range.date(),
                'end_date': timezone.now().date(),
                'total_decisions': 0
            },
            'message': 'No decision data available for the selected period'
        }


def get_dashboard_analytics(date_range_days: int = 90) -> Dict[str, Any]:
    """Get comprehensive analytics for dashboard"""
    
    engine = AnalyticsEngine(date_range_days)
    
    return {
        'summary': engine.get_decision_summary(),
        'agency_analysis': engine.get_agency_analysis(),
        'naics_analysis': engine.get_naics_analysis(),
        'trends': engine.get_trend_analysis(),
        'ai_performance': engine.get_ai_performance_metrics(),
        'competitive_intelligence': engine.get_competitive_intelligence(),
        'generated_at': timezone.now().isoformat()
    }