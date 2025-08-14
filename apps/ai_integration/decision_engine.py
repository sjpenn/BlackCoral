"""
BLACK CORAL Intelligent Decision Engine
AI-powered bid/no-bid decision system with multi-factor analysis
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Avg, Count

from .ai_providers import ai_manager, AIRequest, ModelType
from .services import OpportunityAnalysis
from apps.opportunities.models import Opportunity
from apps.core.models import NAICSCode

logger = logging.getLogger(__name__)


@dataclass
class DecisionFactors:
    """Factors considered in bid/no-bid decisions"""
    # Strategic Factors
    strategic_alignment: float  # 0.0-1.0
    capability_match: float
    market_position: float
    
    # Financial Factors
    estimated_value: float
    profit_potential: float
    resource_requirements: float
    
    # Risk Factors
    technical_risk: float
    schedule_risk: float
    competitive_risk: float
    
    # Historical Factors
    past_performance: float
    agency_relationship: float
    success_probability: float


@dataclass
class BidDecision:
    """Bid/no-bid decision with rationale"""
    recommendation: str  # BID, NO_BID, WATCH
    confidence_score: float  # 0.0-1.0
    overall_score: float  # 0.0-100.0
    factors: DecisionFactors
    rationale: str
    key_strengths: List[str]
    key_concerns: List[str]
    action_items: List[str]
    estimated_bid_cost: Optional[float]
    win_probability: Optional[float]


class DecisionEngine:
    """Intelligent bid/no-bid decision engine"""
    
    # Decision thresholds
    BID_THRESHOLD = 70.0
    WATCH_THRESHOLD = 50.0
    
    # Factor weights for overall scoring
    WEIGHTS = {
        'strategic_alignment': 0.20,
        'capability_match': 0.18,
        'market_position': 0.12,
        'estimated_value': 0.15,
        'profit_potential': 0.10,
        'resource_requirements': 0.05,
        'technical_risk': 0.08,
        'schedule_risk': 0.05,
        'competitive_risk': 0.07
    }
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DecisionEngine")
    
    def evaluate_opportunity(self, opportunity: Opportunity, 
                           ai_analysis: OpportunityAnalysis,
                           usaspending_context: Dict[str, Any] = None) -> BidDecision:
        """
        Comprehensive opportunity evaluation for bid/no-bid decision
        """
        self.logger.info(f"Evaluating opportunity: {opportunity.solicitation_number}")
        
        # Calculate decision factors
        factors = self._calculate_decision_factors(opportunity, ai_analysis, usaspending_context)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(factors)
        
        # Make recommendation
        recommendation = self._make_recommendation(overall_score, factors)
        
        # Generate rationale using AI
        rationale, strengths, concerns, actions = self._generate_rationale(
            opportunity, ai_analysis, factors, overall_score, recommendation
        )
        
        # Estimate bid costs and win probability
        bid_cost = self._estimate_bid_cost(opportunity, ai_analysis)
        win_probability = self._estimate_win_probability(factors, overall_score)
        
        decision = BidDecision(
            recommendation=recommendation,
            confidence_score=ai_analysis.confidence_score,
            overall_score=overall_score,
            factors=factors,
            rationale=rationale,
            key_strengths=strengths,
            key_concerns=concerns,
            action_items=actions,
            estimated_bid_cost=bid_cost,
            win_probability=win_probability
        )
        
        self.logger.info(f"Decision: {recommendation} (Score: {overall_score:.1f})")
        return decision
    
    def _calculate_decision_factors(self, opportunity: Opportunity,
                                  ai_analysis: OpportunityAnalysis,
                                  usaspending_context: Dict[str, Any] = None) -> DecisionFactors:
        """Calculate all decision factors"""
        
        # Strategic Factors
        strategic_alignment = self._assess_strategic_alignment(opportunity, ai_analysis)
        capability_match = self._assess_capability_match(opportunity, ai_analysis)
        market_position = self._assess_market_position(opportunity, usaspending_context)
        
        # Financial Factors
        estimated_value = self._assess_estimated_value(opportunity)
        profit_potential = self._assess_profit_potential(opportunity, ai_analysis)
        resource_requirements = self._assess_resource_requirements(opportunity, ai_analysis)
        
        # Risk Factors
        technical_risk = self._assess_technical_risk(opportunity, ai_analysis)
        schedule_risk = self._assess_schedule_risk(opportunity, ai_analysis)
        competitive_risk = self._assess_competitive_risk(opportunity, usaspending_context)
        
        # Historical Factors (placeholder - would integrate with performance data)
        past_performance = 0.7  # Default assumption
        agency_relationship = 0.6  # Default assumption
        success_probability = self._calculate_success_probability(opportunity, ai_analysis)
        
        return DecisionFactors(
            strategic_alignment=strategic_alignment,
            capability_match=capability_match,
            market_position=market_position,
            estimated_value=estimated_value,
            profit_potential=profit_potential,
            resource_requirements=resource_requirements,
            technical_risk=technical_risk,
            schedule_risk=schedule_risk,
            competitive_risk=competitive_risk,
            past_performance=past_performance,
            agency_relationship=agency_relationship,
            success_probability=success_probability
        )
    
    def _assess_strategic_alignment(self, opportunity: Opportunity, 
                                  ai_analysis: OpportunityAnalysis) -> float:
        """Assess strategic alignment with business objectives"""
        
        # Analyze keywords for strategic terms
        strategic_keywords = ['innovation', 'emerging', 'strategic', 'critical', 'mission']
        keyword_match = sum(1 for keyword in ai_analysis.keywords 
                           if any(term in keyword.lower() for term in strategic_keywords))
        
        # NAICS code alignment (simplified)
        target_naics = ['541330', '541511', '541512', '541513', '541519']  # Engineering/IT services
        naics_alignment = 0.8 if any(code in target_naics 
                                   for code in opportunity.naics_codes.values_list('code', flat=True)) else 0.4
        
        # Agency preference (simplified)
        preferred_agencies = ['Department of Defense', 'Department of Energy', 'NASA']
        agency_alignment = 0.9 if opportunity.agency and opportunity.agency.name in preferred_agencies else 0.6
        
        # Combine factors
        strategic_score = (
            (keyword_match / 10 * 0.3) +  # Normalize keyword match
            (naics_alignment * 0.4) +
            (agency_alignment * 0.3)
        )
        
        return min(strategic_score, 1.0)
    
    def _assess_capability_match(self, opportunity: Opportunity,
                               ai_analysis: OpportunityAnalysis) -> float:
        """Assess capability match based on technical requirements"""
        
        # Analyze technical requirements for capability keywords
        capability_keywords = [
            'software development', 'system integration', 'cybersecurity',
            'cloud computing', 'data analytics', 'artificial intelligence',
            'engineering', 'consulting', 'project management'
        ]
        
        # Check requirements against capabilities
        req_text = ' '.join(ai_analysis.technical_requirements).lower()
        capability_matches = sum(1 for keyword in capability_keywords 
                               if keyword in req_text)
        
        # Normalize based on number of requirements and confidence
        capability_score = min(capability_matches / 5 * ai_analysis.confidence_score, 1.0)
        
        return capability_score
    
    def _assess_market_position(self, opportunity: Opportunity,
                              usaspending_context: Dict[str, Any] = None) -> float:
        """Assess market position based on competition and historical data"""
        
        base_score = 0.6  # Default market position
        
        if usaspending_context:
            # Analyze top contractors
            top_contractors = usaspending_context.get('top_contractors', {})
            if top_contractors and 'results' in top_contractors:
                # Higher score if market is fragmented (many small contractors)
                contractor_count = len(top_contractors['results'])
                if contractor_count > 10:
                    base_score += 0.2  # Fragmented market is good
                elif contractor_count < 5:
                    base_score -= 0.1  # Concentrated market is challenging
        
        # Set-aside opportunities improve position
        if opportunity.set_aside_type and 'small business' in opportunity.set_aside_type.lower():
            base_score += 0.15
        
        return min(base_score, 1.0)
    
    def _assess_estimated_value(self, opportunity: Opportunity) -> float:
        """Assess opportunity value attractiveness"""
        
        # Extract value from description (simplified approach)
        value_score = 0.5  # Default
        
        if opportunity.description:
            desc_lower = opportunity.description.lower()
            
            # Look for value indicators
            if 'million' in desc_lower:
                if 'hundred million' in desc_lower or '$100' in desc_lower:
                    value_score = 0.95
                elif any(f'${i}' in desc_lower for i in range(50, 100)):
                    value_score = 0.85
                elif any(f'${i}' in desc_lower for i in range(10, 50)):
                    value_score = 0.75
                else:
                    value_score = 0.65
            elif 'billion' in desc_lower:
                value_score = 1.0
            elif any(f'${i}k' in desc_lower for i in range(500, 10000)):
                value_score = 0.6
        
        return value_score
    
    def _assess_profit_potential(self, opportunity: Opportunity,
                               ai_analysis: OpportunityAnalysis) -> float:
        """Assess profit potential based on opportunity characteristics"""
        
        # Base profit potential
        profit_score = 0.6
        
        # Higher profit for innovative/R&D work
        if any(term in ai_analysis.business_opportunity.lower() 
               for term in ['research', 'development', 'innovation', 'prototype']):
            profit_score += 0.2
        
        # Lower profit for commoditized services
        if any(term in ai_analysis.business_opportunity.lower()
               for term in ['maintenance', 'support', 'operations']):
            profit_score -= 0.1
        
        # Contract type affects profit potential
        if opportunity.opportunity_type:
            if 'indefinite delivery' in opportunity.opportunity_type.lower():
                profit_score += 0.1  # IDIQ contracts often have good margins
        
        return min(profit_score, 1.0)
    
    def _assess_resource_requirements(self, opportunity: Opportunity,
                                    ai_analysis: OpportunityAnalysis) -> float:
        """Assess resource requirement burden (inverse scoring)"""
        
        # Analyze technical requirements complexity
        req_count = len(ai_analysis.technical_requirements)
        
        # More requirements = higher resource needs = lower score
        if req_count > 15:
            resource_score = 0.3
        elif req_count > 10:
            resource_score = 0.5
        elif req_count > 5:
            resource_score = 0.7
        else:
            resource_score = 0.9
        
        # Adjust for timeline pressure
        if opportunity.response_date:
            days_to_respond = (opportunity.response_date.date() - timezone.now().date()).days
            if days_to_respond < 14:
                resource_score -= 0.2  # Rush job requires more resources
            elif days_to_respond > 60:
                resource_score += 0.1  # Plenty of time
        
        return max(resource_score, 0.1)
    
    def _assess_technical_risk(self, opportunity: Opportunity,
                             ai_analysis: OpportunityAnalysis) -> float:
        """Assess technical risk (inverse scoring)"""
        
        # Look for risk indicators in AI analysis
        risk_keywords = ['cutting-edge', 'experimental', 'unproven', 'new technology',
                        'research', 'breakthrough', 'novel', 'innovative']
        
        risk_indicators = sum(1 for keyword in risk_keywords
                            if keyword in ai_analysis.risk_assessment.lower())
        
        # Higher risk indicators = lower score (inverse)
        technical_risk_score = max(0.9 - (risk_indicators * 0.15), 0.1)
        
        return technical_risk_score
    
    def _assess_schedule_risk(self, opportunity: Opportunity,
                            ai_analysis: OpportunityAnalysis) -> float:
        """Assess schedule risk (inverse scoring)"""
        
        schedule_risk_score = 0.7  # Default
        
        # Tight deadlines increase risk
        if opportunity.response_date:
            days_to_respond = (opportunity.response_date.date() - timezone.now().date()).days
            if days_to_respond < 7:
                schedule_risk_score = 0.2
            elif days_to_respond < 14:
                schedule_risk_score = 0.4
            elif days_to_respond < 30:
                schedule_risk_score = 0.6
        
        # Look for schedule pressure indicators
        if 'urgent' in ai_analysis.risk_assessment.lower() or 'tight schedule' in ai_analysis.risk_assessment.lower():
            schedule_risk_score -= 0.2
        
        return max(schedule_risk_score, 0.1)
    
    def _assess_competitive_risk(self, opportunity: Opportunity,
                               usaspending_context: Dict[str, Any] = None) -> float:
        """Assess competitive landscape risk (inverse scoring)"""
        
        competitive_risk_score = 0.6  # Default
        
        # Set-aside reduces competition
        if opportunity.set_aside_type:
            if 'small business' in opportunity.set_aside_type.lower():
                competitive_risk_score += 0.2
            elif 'hubzone' in opportunity.set_aside_type.lower():
                competitive_risk_score += 0.3
        
        # Large contracts attract more competition
        if 'million' in opportunity.description.lower():
            competitive_risk_score -= 0.15
        
        return max(competitive_risk_score, 0.1)
    
    def _calculate_success_probability(self, opportunity: Opportunity,
                                     ai_analysis: OpportunityAnalysis) -> float:
        """Calculate overall success probability"""
        
        # Base probability from AI confidence
        base_prob = ai_analysis.confidence_score * 0.7
        
        # Adjust for opportunity characteristics
        if opportunity.set_aside_type and 'small business' in opportunity.set_aside_type.lower():
            base_prob += 0.1
        
        # Agency familiarity (simplified)
        familiar_agencies = ['Department of Defense', 'Department of Energy']
        if opportunity.agency and opportunity.agency.name in familiar_agencies:
            base_prob += 0.05
        
        return min(base_prob, 0.95)
    
    def _calculate_overall_score(self, factors: DecisionFactors) -> float:
        """Calculate weighted overall score"""
        
        # Positive factors (higher is better)
        positive_score = (
            factors.strategic_alignment * self.WEIGHTS['strategic_alignment'] +
            factors.capability_match * self.WEIGHTS['capability_match'] +
            factors.market_position * self.WEIGHTS['market_position'] +
            factors.estimated_value * self.WEIGHTS['estimated_value'] +
            factors.profit_potential * self.WEIGHTS['profit_potential']
        )
        
        # Risk factors (lower risk = higher score, so we invert)
        risk_score = (
            factors.technical_risk * self.WEIGHTS['technical_risk'] +
            factors.schedule_risk * self.WEIGHTS['schedule_risk'] +
            factors.competitive_risk * self.WEIGHTS['competitive_risk']
        )
        
        # Resource requirements (lower is better, so we invert)
        resource_score = factors.resource_requirements * self.WEIGHTS['resource_requirements']
        
        overall_score = (positive_score + risk_score + resource_score) * 100
        
        return min(overall_score, 100.0)
    
    def _make_recommendation(self, overall_score: float, factors: DecisionFactors) -> str:
        """Make bid/no-bid/watch recommendation"""
        
        if overall_score >= self.BID_THRESHOLD:
            return "BID"
        elif overall_score >= self.WATCH_THRESHOLD:
            return "WATCH"
        else:
            return "NO_BID"
    
    def _generate_rationale(self, opportunity: Opportunity,
                          ai_analysis: OpportunityAnalysis,
                          factors: DecisionFactors,
                          overall_score: float,
                          recommendation: str) -> Tuple[str, List[str], List[str], List[str]]:
        """Generate AI-powered decision rationale"""
        
        prompt = f"""
Generate a bid/no-bid decision rationale for this government contracting opportunity:

OPPORTUNITY: {opportunity.title}
AGENCY: {opportunity.agency.name if opportunity.agency else 'Unknown'}
RECOMMENDATION: {recommendation}
OVERALL SCORE: {overall_score:.1f}/100

DECISION FACTORS:
- Strategic Alignment: {factors.strategic_alignment:.2f}
- Capability Match: {factors.capability_match:.2f} 
- Market Position: {factors.market_position:.2f}
- Estimated Value: {factors.estimated_value:.2f}
- Profit Potential: {factors.profit_potential:.2f}
- Technical Risk: {factors.technical_risk:.2f}
- Schedule Risk: {factors.schedule_risk:.2f}
- Competitive Risk: {factors.competitive_risk:.2f}

AI ANALYSIS SUMMARY: {ai_analysis.executive_summary}

Provide:
1. A clear rationale (2-3 sentences) for the {recommendation} recommendation
2. Key Strengths (3-5 bullet points)
3. Key Concerns (3-5 bullet points) 
4. Action Items (3-5 bullet points)

Format as structured text with clear sections.
"""
        
        try:
            request = AIRequest(
                prompt=prompt,
                system_prompt="You are a government contracting decision advisor. Provide structured, actionable analysis.",
                model_type=ModelType.ANALYSIS,
                max_tokens=1500,
                temperature=0.3
            )
            
            response = ai_manager.generate_response(request)
            
            # Parse response (simplified)
            content = response.content
            
            # Extract sections (basic parsing)
            rationale = "Based on comprehensive analysis, this recommendation optimizes strategic value and risk management."
            strengths = ["Strategic alignment with business objectives", "Strong capability match"]
            concerns = ["Competitive landscape requires careful positioning", "Timeline considerations"]
            actions = ["Develop detailed technical approach", "Assess team availability"]
            
            # Try to extract actual content from AI response
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if 'rationale' in line.lower() and ':' in line:
                    current_section = 'rationale'
                elif 'strength' in line.lower():
                    current_section = 'strengths'
                    strengths = []
                elif 'concern' in line.lower():
                    current_section = 'concerns'
                    concerns = []
                elif 'action' in line.lower():
                    current_section = 'actions'
                    actions = []
                elif line and current_section:
                    if current_section == 'rationale' and not line.startswith('•') and not line.startswith('-'):
                        rationale = line
                    elif line.startswith('•') or line.startswith('-'):
                        content_item = line[1:].strip()
                        if current_section == 'strengths':
                            strengths.append(content_item)
                        elif current_section == 'concerns':
                            concerns.append(content_item)
                        elif current_section == 'actions':
                            actions.append(content_item)
            
            return rationale, strengths, concerns, actions
            
        except Exception as e:
            logger.warning(f"Failed to generate AI rationale: {e}")
            
            # Fallback rationale
            fallback_rationale = f"Score: {overall_score:.1f}/100 leads to {recommendation} recommendation based on strategic alignment, capability match, and risk assessment."
            fallback_strengths = ["Quantitative analysis completed", "Multiple factors considered"]
            fallback_concerns = ["Market dynamics require monitoring", "Resource allocation needs validation"]
            fallback_actions = ["Review technical approach", "Validate resource availability", "Monitor competition"]
            
            return fallback_rationale, fallback_strengths, fallback_concerns, fallback_actions
    
    def _estimate_bid_cost(self, opportunity: Opportunity,
                          ai_analysis: OpportunityAnalysis) -> Optional[float]:
        """Estimate cost to prepare bid proposal"""
        
        # Base cost factors
        base_cost = 25000  # Base proposal cost
        
        # Adjust for complexity
        req_count = len(ai_analysis.technical_requirements)
        complexity_multiplier = 1 + (req_count * 0.1)
        
        # Adjust for timeline
        if opportunity.response_date:
            days_to_respond = (opportunity.response_date.date() - timezone.now().date()).days
            if days_to_respond < 14:
                timeline_multiplier = 1.5  # Rush job costs more
            elif days_to_respond > 60:
                timeline_multiplier = 0.9   # More time = efficiency
            else:
                timeline_multiplier = 1.0
        else:
            timeline_multiplier = 1.0
        
        estimated_cost = base_cost * complexity_multiplier * timeline_multiplier
        
        return round(estimated_cost, -3)  # Round to nearest thousand
    
    def _estimate_win_probability(self, factors: DecisionFactors, overall_score: float) -> Optional[float]:
        """Estimate probability of winning the contract"""
        
        # Base probability from overall score
        base_prob = overall_score / 100 * 0.4  # Max 40% from score
        
        # Add specific factor contributions
        capability_contribution = factors.capability_match * 0.25
        strategic_contribution = factors.strategic_alignment * 0.15
        competitive_contribution = factors.competitive_risk * 0.20  # Higher competitive risk = lower prob
        
        win_probability = base_prob + capability_contribution + strategic_contribution + competitive_contribution
        
        return min(win_probability, 0.85)  # Cap at 85% (be realistic)


# Convenience function
def evaluate_opportunity_decision(opportunity: Opportunity) -> Optional[BidDecision]:
    """Evaluate opportunity for bid/no-bid decision"""
    
    if not opportunity.ai_analysis_complete:
        logger.warning(f"Opportunity {opportunity.id} needs AI analysis first")
        return None
    
    # Reconstruct AI analysis from stored data
    analysis_data = opportunity.ai_analysis_data
    ai_analysis = OpportunityAnalysis(
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
    
    # Get USASpending context if available
    usaspending_context = opportunity.usaspending_data if opportunity.usaspending_analyzed else None
    
    # Run decision engine
    engine = DecisionEngine()
    decision = engine.evaluate_opportunity(opportunity, ai_analysis, usaspending_context)
    
    return decision