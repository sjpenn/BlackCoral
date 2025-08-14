"""
AI services for opportunity analysis, content generation, and compliance checking
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .ai_providers import ai_manager, AIRequest, ModelType, AIProvider

logger = logging.getLogger(__name__)


@dataclass
class OpportunityAnalysis:
    """Structured opportunity analysis results"""
    executive_summary: str
    technical_requirements: List[str]
    business_opportunity: str
    risk_assessment: str
    compliance_notes: str
    competitive_landscape: str
    recommendation: str
    confidence_score: float
    keywords: List[str]


@dataclass
class ComplianceCheck:
    """Compliance analysis results"""
    overall_status: str  # COMPLIANT, NON_COMPLIANT, NEEDS_REVIEW
    issues: List[Dict[str, str]]
    requirements_met: List[str]
    requirements_missing: List[str]
    recommendations: List[str]
    confidence_score: float


class OpportunityAnalysisService:
    """Service for AI-powered opportunity analysis"""
    
    def __init__(self, preferred_provider: Optional[AIProvider] = None):
        self.preferred_provider = preferred_provider
    
    def analyze_opportunity(self, opportunity_data: Dict[str, Any], 
                          usaspending_data: Dict[str, Any] = None) -> OpportunityAnalysis:
        """Comprehensive opportunity analysis using AI"""
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(opportunity_data, usaspending_data)
        
        system_prompt = """You are an expert government contracting analyst specializing in federal procurement opportunities. Analyze the given opportunity and provide a comprehensive assessment that includes:

1. Executive Summary (2-3 sentences)
2. Key Technical Requirements (bullet points)
3. Business Opportunity Assessment (market size, potential value)
4. Risk Assessment (technical, schedule, competitive risks)
5. Compliance Considerations
6. Competitive Landscape Analysis
7. Strategic Recommendation (pursue/pass/watch)
8. Confidence Score (0.0-1.0)
9. Key Search Keywords

Provide structured, actionable insights that help determine bid/no-bid decisions. Be concise but thorough."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model_type=ModelType.ANALYSIS,
            max_tokens=3000,
            temperature=0.3
        )
        
        try:
            response = ai_manager.generate_response(
                request, 
                preferred_provider=self.preferred_provider
            )
            
            # Parse AI response into structured format
            analysis = self._parse_analysis_response(response.content)
            
            logger.info(f"Opportunity analysis completed using {response.provider.value}")
            return analysis
            
        except Exception as e:
            logger.error(f"Opportunity analysis failed: {e}")
            raise
    
    def _build_analysis_prompt(self, opportunity_data: Dict[str, Any], 
                             usaspending_data: Dict[str, Any] = None) -> str:
        """Build comprehensive analysis prompt"""
        
        prompt_parts = [
            "GOVERNMENT CONTRACTING OPPORTUNITY ANALYSIS",
            "=" * 50,
            "",
            "OPPORTUNITY DETAILS:",
            f"Title: {opportunity_data.get('title', 'N/A')}",
            f"Solicitation Number: {opportunity_data.get('solicitation_number', 'N/A')}",
            f"Agency: {opportunity_data.get('agency_name', 'N/A')}",
            f"Posted Date: {opportunity_data.get('posted_date', 'N/A')}",
            f"Response Due: {opportunity_data.get('response_date', 'N/A')}",
            f"Set-Aside Type: {opportunity_data.get('set_aside_type', 'N/A')}",
            "",
            "DESCRIPTION:",
            opportunity_data.get('description', 'No description available'),
            ""
        ]
        
        # Add NAICS codes if available
        if opportunity_data.get('naics_codes'):
            prompt_parts.extend([
                "NAICS CODES:",
                ', '.join(opportunity_data['naics_codes']),
                ""
            ])
        
        # Add USASpending context if available
        if usaspending_data:
            prompt_parts.extend([
                "HISTORICAL SPENDING CONTEXT:",
                f"Previous agency spending patterns available: {bool(usaspending_data.get('agency_spending'))}",
                f"NAICS-specific spending trends available: {bool(usaspending_data.get('naics_spending'))}",
                f"Similar past awards identified: {bool(usaspending_data.get('similar_awards'))}",
                ""
            ])
        
        # Add specific fields if present
        if opportunity_data.get('place_of_performance'):
            prompt_parts.extend([
                "PLACE OF PERFORMANCE:",
                str(opportunity_data['place_of_performance']),
                ""
            ])
        
        if opportunity_data.get('point_of_contact'):
            prompt_parts.extend([
                "POINT OF CONTACT AVAILABLE: Yes",
                ""
            ])
        
        prompt_parts.extend([
            "Please provide a comprehensive analysis following the structured format requested."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_analysis_response(self, response_content: str) -> OpportunityAnalysis:
        """Parse AI response into structured analysis"""
        
        # Simple parsing - in production, you might use more sophisticated NLP
        lines = response_content.split('\n')
        
        # Default values
        analysis_data = {
            'executive_summary': '',
            'technical_requirements': [],
            'business_opportunity': '',
            'risk_assessment': '',
            'compliance_notes': '',
            'competitive_landscape': '',
            'recommendation': '',
            'confidence_score': 0.7,
            'keywords': []
        }
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect sections
            lower_line = line.lower()
            if 'executive summary' in lower_line:
                current_section = 'executive_summary'
                current_content = []
            elif 'technical requirement' in lower_line:
                current_section = 'technical_requirements'
                current_content = []
            elif 'business opportunity' in lower_line:
                current_section = 'business_opportunity'
                current_content = []
            elif 'risk assessment' in lower_line:
                current_section = 'risk_assessment'
                current_content = []
            elif 'compliance' in lower_line:
                current_section = 'compliance_notes'
                current_content = []
            elif 'competitive landscape' in lower_line:
                current_section = 'competitive_landscape'
                current_content = []
            elif 'recommendation' in lower_line:
                current_section = 'recommendation'
                current_content = []
            elif 'confidence score' in lower_line:
                # Extract confidence score
                import re
                score_match = re.search(r'(\d+\.?\d*)', line)
                if score_match:
                    score = float(score_match.group(1))
                    if score > 1.0:
                        score = score / 100  # Convert percentage
                    analysis_data['confidence_score'] = score
                continue
            elif 'keywords' in lower_line:
                current_section = 'keywords'
                current_content = []
            else:
                # Add content to current section
                if current_section and line:
                    if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                        # Bullet point
                        if current_section == 'technical_requirements':
                            analysis_data['technical_requirements'].append(line[1:].strip())
                        elif current_section == 'keywords':
                            # Split keywords
                            keywords = line[1:].strip().split(',')
                            analysis_data['keywords'].extend([k.strip() for k in keywords])
                        else:
                            current_content.append(line)
                    else:
                        current_content.append(line)
        
        # Finalize content for non-list sections
        for section in ['executive_summary', 'business_opportunity', 'risk_assessment', 
                       'compliance_notes', 'competitive_landscape', 'recommendation']:
            if section in analysis_data and isinstance(analysis_data[section], str):
                # Join collected content
                section_content = []
                collecting = False
                for line in lines:
                    if section.replace('_', ' ') in line.lower():
                        # Found section header, start collecting
                        collecting = True
                        continue
                    elif collecting and any(other_section.replace('_', ' ') in line.lower() 
                                         for other_section in analysis_data.keys()):
                        # Hit next section, stop collecting
                        break
                    elif collecting:
                        section_content.append(line.strip())
                
                analysis_data[section] = ' '.join(section_content).strip()
        
        # Fallback: use full response if parsing failed
        if not analysis_data['executive_summary']:
            analysis_data['executive_summary'] = response_content[:200] + "..."
        
        return OpportunityAnalysis(**analysis_data)


class ComplianceService:
    """AI-powered compliance checking service"""
    
    def __init__(self, preferred_provider: Optional[AIProvider] = None):
        self.preferred_provider = preferred_provider
    
    def check_compliance(self, opportunity_data: Dict[str, Any],
                        proposal_content: str = None) -> ComplianceCheck:
        """Check opportunity compliance requirements"""
        
        prompt = self._build_compliance_prompt(opportunity_data, proposal_content)
        
        system_prompt = """You are a government contracting compliance expert. Analyze the opportunity for compliance requirements and assess proposal alignment. Provide:

1. Overall Status: COMPLIANT, NON_COMPLIANT, or NEEDS_REVIEW
2. Specific Issues (if any) with descriptions
3. Requirements Met (list what's satisfied)
4. Requirements Missing (list what's needed)
5. Recommendations for compliance
6. Confidence Score (0.0-1.0)

Focus on federal acquisition regulations, set-aside requirements, technical specifications, and submission requirements."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model_type=ModelType.CLASSIFICATION,
            max_tokens=2000,
            temperature=0.2
        )
        
        try:
            response = ai_manager.generate_response(
                request,
                preferred_provider=self.preferred_provider
            )
            
            compliance_check = self._parse_compliance_response(response.content)
            
            logger.info(f"Compliance check completed using {response.provider.value}")
            return compliance_check
            
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            raise
    
    def _build_compliance_prompt(self, opportunity_data: Dict[str, Any],
                               proposal_content: str = None) -> str:
        """Build compliance checking prompt"""
        
        prompt_parts = [
            "GOVERNMENT CONTRACTING COMPLIANCE ANALYSIS",
            "=" * 50,
            "",
            "OPPORTUNITY COMPLIANCE REQUIREMENTS:",
            f"Solicitation: {opportunity_data.get('solicitation_number', 'N/A')}",
            f"Agency: {opportunity_data.get('agency_name', 'N/A')}",
            f"Set-Aside Type: {opportunity_data.get('set_aside_type', 'N/A')}",
            f"Opportunity Type: {opportunity_data.get('opportunity_type', 'N/A')}",
            "",
            "OPPORTUNITY DESCRIPTION:",
            opportunity_data.get('description', 'No description available'),
            ""
        ]
        
        if proposal_content:
            prompt_parts.extend([
                "PROPOSAL CONTENT TO EVALUATE:",
                proposal_content[:2000],  # Limit length
                ""
            ])
        
        prompt_parts.extend([
            "Please analyze compliance requirements and provide structured assessment."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_compliance_response(self, response_content: str) -> ComplianceCheck:
        """Parse compliance response into structured format"""
        
        # Simple parsing - extract key information
        lines = response_content.split('\n')
        
        compliance_data = {
            'overall_status': 'NEEDS_REVIEW',
            'issues': [],
            'requirements_met': [],
            'requirements_missing': [],
            'recommendations': [],
            'confidence_score': 0.5
        }
        
        # Extract overall status
        for line in lines:
            if 'COMPLIANT' in line.upper() and 'NON' not in line.upper():
                compliance_data['overall_status'] = 'COMPLIANT'
                break
            elif 'NON_COMPLIANT' in line.upper() or 'NON-COMPLIANT' in line.upper():
                compliance_data['overall_status'] = 'NON_COMPLIANT'
                break
        
        # Extract confidence score
        import re
        for line in lines:
            if 'confidence' in line.lower():
                score_match = re.search(r'(\d+\.?\d*)', line)
                if score_match:
                    score = float(score_match.group(1))
                    if score > 1.0:
                        score = score / 100
                    compliance_data['confidence_score'] = score
                    break
        
        return ComplianceCheck(**compliance_data)


class ContentGenerationService:
    """AI-powered content generation for proposals and summaries"""
    
    def __init__(self, preferred_provider: Optional[AIProvider] = None):
        self.preferred_provider = preferred_provider
    
    def generate_proposal_outline(self, opportunity_data: Dict[str, Any],
                                analysis: OpportunityAnalysis) -> str:
        """Generate proposal outline based on opportunity analysis"""
        
        prompt = f"""
PROPOSAL OUTLINE GENERATION

Opportunity: {opportunity_data.get('title', 'N/A')}
Agency: {opportunity_data.get('agency_name', 'N/A')}

Analysis Summary:
{analysis.executive_summary}

Technical Requirements:
{chr(10).join(['• ' + req for req in analysis.technical_requirements])}

Generate a comprehensive proposal outline that addresses:
1. Executive Summary
2. Technical Approach
3. Management Plan
4. Past Performance
5. Pricing Strategy
6. Risk Mitigation

Tailor the outline to this specific opportunity and requirements.
"""
        
        request = AIRequest(
            prompt=prompt,
            model_type=ModelType.GENERATION,
            max_tokens=2000,
            temperature=0.4
        )
        
        try:
            response = ai_manager.generate_response(
                request,
                preferred_provider=self.preferred_provider
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"Proposal outline generation failed: {e}")
            raise
    
    def generate_executive_summary(self, opportunity_data: Dict[str, Any],
                                 analysis: OpportunityAnalysis) -> str:
        """Generate executive summary for opportunity"""
        
        prompt = f"""
Generate a compelling executive summary for this government contracting opportunity:

Opportunity: {opportunity_data.get('title', 'N/A')}
Agency: {opportunity_data.get('agency_name', 'N/A')}
Value Assessment: {analysis.business_opportunity}

The executive summary should be professional, concise (2-3 paragraphs), and highlight:
- Why this opportunity aligns with organizational capabilities
- Key value propositions
- Competitive advantages
- Expected outcomes

Make it persuasive for decision-makers reviewing bid/no-bid decisions.
"""
        
        request = AIRequest(
            prompt=prompt,
            model_type=ModelType.GENERATION,
            max_tokens=1000,
            temperature=0.5
        )
        
        try:
            response = ai_manager.generate_response(
                request,
                preferred_provider=self.preferred_provider
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            raise