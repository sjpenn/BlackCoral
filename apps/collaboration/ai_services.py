"""
AI Enhancement Services for Proposal Sections
Provides intelligent writing assistance and content optimization
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from apps.ai_integration.ai_providers import AIManager, AIRequest

logger = logging.getLogger(__name__)


class SectionAIEnhancer:
    """
    AI-powered section enhancement service
    """
    
    def __init__(self):
        self.ai_manager = AIManager()
    
    def enhance_content(self, content: str, section_title: str, requirements: str = "", 
                       enhancement_type: str = "improve") -> Dict:
        """
        Enhance section content using AI
        
        Args:
            content: Current section content (HTML)
            section_title: Title of the section
            requirements: Section requirements/guidelines
            enhancement_type: Type of enhancement (improve, expand, clarify, etc.)
        
        Returns:
            Dict with enhanced content and suggestions
        """
        try:
            # Create enhancement prompt based on type
            prompt = self._create_enhancement_prompt(
                content, section_title, requirements, enhancement_type
            )
            
            request = AIRequest(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                max_tokens=4000,
                temperature=0.7
            )
            
            response = self.ai_manager.generate_response(request)
            return self._parse_enhancement_response(response.content)
                
        except Exception as e:
            logger.error(f"Section AI enhancement error: {str(e)}")
            return {"error": "AI enhancement service temporarily unavailable"}
    
    def generate_outline(self, section_title: str, requirements: str, 
                        word_count_target: int = None) -> Dict:
        """Generate section outline using AI"""
        try:
            prompt = f"""
            Create a detailed outline for a government proposal section titled "{section_title}".
            
            Requirements: {requirements or "Standard government proposal section"}
            Target Word Count: {word_count_target or "Not specified"}
            
            Generate a structured outline with:
            1. Main topics and subtopics
            2. Key points to address
            3. Suggested content flow
            4. Compliance considerations
            
            Format as JSON with hierarchical structure.
            """
            
            request = AIRequest(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                max_tokens=2000,
                temperature=0.8
            )
            
            response = self.ai_manager.generate_response(request)
            
            try:
                outline_data = json.loads(response.content)
                return {"success": True, "outline": outline_data}
            except json.JSONDecodeError:
                # Fallback to text format
                return {"success": True, "outline_text": response.content}
                
        except Exception as e:
            logger.error(f"Outline generation error: {str(e)}")
            return {"error": "Outline generation service temporarily unavailable"}
    
    def check_compliance(self, content: str, section_title: str, 
                        requirements: str = "") -> Dict:
        """Check section compliance with requirements"""
        try:
            prompt = f"""
            Review this government proposal section for compliance and completeness:
            
            Section Title: {section_title}
            Requirements: {requirements or "Standard government proposal requirements"}
            Content: {self._strip_html(content)}
            
            Analyze for:
            1. Completeness - Are all required elements addressed?
            2. Compliance - Does it meet government proposal standards?
            3. Clarity - Is the content clear and well-structured?
            4. Missing elements - What's missing or needs improvement?
            
            Provide specific, actionable feedback.
            """
            
            request = AIRequest(
                prompt=prompt,
                system_prompt=self._get_compliance_system_prompt(),
                max_tokens=2000,
                temperature=0.3
            )
            
            response = self.ai_manager.generate_response(request)
            return self._parse_compliance_response(response.content)
                
        except Exception as e:
            logger.error(f"Compliance check error: {str(e)}")
            return {"error": "Compliance check service temporarily unavailable"}
    
    def suggest_improvements(self, content: str, section_title: str,
                           word_count_current: int, word_count_target: int = None) -> Dict:
        """Provide specific improvement suggestions"""
        try:
            prompt = f"""
            Analyze this proposal section and provide specific improvement suggestions:
            
            Section: {section_title}
            Current Word Count: {word_count_current}
            Target Word Count: {word_count_target or "Not specified"}
            Content: {self._strip_html(content)}
            
            Provide suggestions for:
            1. Content improvements (specific text changes)
            2. Structure enhancements
            3. Word count optimization (if target specified)
            4. Persuasiveness and impact
            5. Technical accuracy
            
            Be specific and actionable.
            """
            
            request = AIRequest(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                max_tokens=3000,
                temperature=0.6
            )
            
            response = self.ai_manager.generate_response(request)
            return self._parse_suggestions_response(response.content)
                
        except Exception as e:
            logger.error(f"Suggestions generation error: {str(e)}")
            return {"error": "Suggestions service temporarily unavailable"}
    
    def expand_content(self, content: str, section_title: str, 
                      target_expansion: str = "") -> Dict:
        """Expand existing content with additional detail"""
        try:
            prompt = f"""
            Expand and enhance this proposal section content:
            
            Section: {section_title}
            Current Content: {self._strip_html(content)}
            Focus Area: {target_expansion or "General expansion and detail"}
            
            Expand the content by:
            1. Adding relevant technical details
            2. Including supporting evidence and examples
            3. Enhancing persuasive elements
            4. Maintaining professional government proposal tone
            5. Ensuring logical flow and structure
            
            Return the expanded content in HTML format.
            """
            
            request = AIRequest(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                max_tokens=4000,
                temperature=0.7
            )
            
            response = self.ai_manager.generate_response(request)
            return {"success": True, "expanded_content": response.content}
                
        except Exception as e:
            logger.error(f"Content expansion error: {str(e)}")
            return {"error": "Content expansion service temporarily unavailable"}
    
    def _create_enhancement_prompt(self, content: str, section_title: str, 
                                 requirements: str, enhancement_type: str) -> str:
        """Create enhancement prompt based on type"""
        
        base_content = self._strip_html(content)
        
        prompts = {
            "improve": f"""
                Improve this government proposal section for clarity, impact, and professionalism:
                
                Section: {section_title}
                Requirements: {requirements}
                Current Content: {base_content}
                
                Enhance by improving clarity, flow, persuasiveness, and technical accuracy.
                Maintain government proposal standards and tone.
            """,
            "expand": f"""
                Expand this proposal section with additional relevant detail:
                
                Section: {section_title}
                Requirements: {requirements}
                Current Content: {base_content}
                
                Add depth, examples, and supporting information while maintaining focus.
            """,
            "clarify": f"""
                Clarify and simplify this proposal section for better readability:
                
                Section: {section_title}
                Requirements: {requirements}
                Current Content: {base_content}
                
                Make the content clearer, more concise, and easier to understand.
            """,
            "strengthen": f"""
                Strengthen the persuasive impact of this proposal section:
                
                Section: {section_title}
                Requirements: {requirements}
                Current Content: {base_content}
                
                Enhance competitive positioning, value proposition, and convincing elements.
            """
        }
        
        return prompts.get(enhancement_type, prompts["improve"])
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for section enhancement"""
        return """
        You are an expert government proposal writer with extensive experience in federal contracting. 
        You understand:
        - Government proposal requirements and evaluation criteria
        - Federal acquisition regulations and compliance needs
        - Persuasive writing techniques for competitive proposals
        - Technical writing standards for government documents
        - Professional tone and formatting expectations
        
        Always maintain:
        - Professional, authoritative tone
        - Clear, concise communication
        - Compliance with government standards
        - Competitive positioning
        - Factual accuracy and credibility
        """
    
    def _get_compliance_system_prompt(self) -> str:
        """Get system prompt for compliance checking"""
        return """
        You are a government proposal compliance specialist with deep knowledge of:
        - Federal acquisition regulations (FAR)
        - Proposal evaluation criteria
        - Government document standards
        - Compliance requirements and best practices
        
        Provide thorough, accurate compliance assessments with specific, actionable recommendations.
        """
    
    def _strip_html(self, content: str) -> str:
        """Remove HTML tags for AI processing"""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', content)
    
    def _parse_enhancement_response(self, response_content: str) -> Dict:
        """Parse AI enhancement response"""
        try:
            # Try to parse as JSON first
            if response_content.strip().startswith('{'):
                return json.loads(response_content)
            else:
                # Treat as enhanced content
                return {
                    "success": True,
                    "enhanced_content": response_content,
                    "suggestions": []
                }
        except json.JSONDecodeError:
            return {
                "success": True,
                "enhanced_content": response_content,
                "suggestions": []
            }
    
    def _parse_compliance_response(self, response_content: str) -> Dict:
        """Parse compliance check response"""
        try:
            if response_content.strip().startswith('{'):
                return json.loads(response_content)
            else:
                # Parse text response
                lines = response_content.split('\n')
                issues = []
                recommendations = []
                
                current_section = None
                for line in lines:
                    line = line.strip()
                    if 'issue' in line.lower() or 'problem' in line.lower():
                        if line:
                            issues.append(line)
                    elif 'recommend' in line.lower() or 'suggest' in line.lower():
                        if line:
                            recommendations.append(line)
                
                return {
                    "success": True,
                    "compliance_score": 75,  # Default score
                    "issues": issues,
                    "recommendations": recommendations,
                    "details": response_content
                }
        except:
            return {
                "success": True,
                "compliance_score": 75,
                "details": response_content
            }
    
    def _parse_suggestions_response(self, response_content: str) -> Dict:
        """Parse suggestions response"""
        try:
            if response_content.strip().startswith('{'):
                return json.loads(response_content)
            else:
                # Parse text response into suggestions
                lines = response_content.split('\n')
                suggestions = []
                
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or 
                               line.startswith('1.') or 'suggest' in line.lower()):
                        suggestions.append({
                            "type": "improvement",
                            "text": line,
                            "priority": "medium"
                        })
                
                return {
                    "success": True,
                    "suggestions": suggestions,
                    "details": response_content
                }
        except:
            return {
                "success": True,
                "suggestions": [{"type": "general", "text": response_content, "priority": "medium"}]
            }


# Initialize global service instance
section_ai_enhancer = SectionAIEnhancer()