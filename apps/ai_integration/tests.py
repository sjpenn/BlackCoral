"""
Tests for AI Integration functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.utils import timezone

from .ai_providers import (
    ClaudeProvider, GeminiProvider, OpenRouterProvider, 
    AIManager, AIRequest, AIResponse, ModelType, AIProvider
)
from .services import OpportunityAnalysisService, ComplianceService, ContentGenerationService
from .models import AITask
from apps.opportunities.models import Opportunity
from apps.core.models import Agency, NAICSCode


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
})
class TestAIProviders(TestCase):
    """Test AI provider implementations"""
    
    def test_claude_provider_initialization(self):
        """Test Claude provider initialization"""
        provider = ClaudeProvider(api_key="test-key")
        self.assertEqual(provider.api_key, "test-key")
        self.assertIn('claude-3-5-sonnet-20241022', provider.get_available_models())
    
    def test_gemini_provider_initialization(self):
        """Test Gemini provider initialization"""
        provider = GeminiProvider(api_key="test-key")
        self.assertEqual(provider.api_key, "test-key")
        self.assertIn('gemini-1.5-pro', provider.get_available_models())
    
    def test_openrouter_provider_initialization(self):
        """Test OpenRouter provider initialization"""
        provider = OpenRouterProvider(
            api_key="test-key",
            site_url="https://test.com",
            site_name="Test Site"
        )
        self.assertEqual(provider.api_key, "test-key")
        self.assertIn('openai/gpt-4o', provider.get_available_models())
    
    def test_model_recommendations(self):
        """Test model recommendations for different task types"""
        provider = ClaudeProvider(api_key="test-key")
        
        # Test different model type recommendations
        analysis_model = provider.get_recommended_model(ModelType.ANALYSIS)
        generation_model = provider.get_recommended_model(ModelType.GENERATION)
        classification_model = provider.get_recommended_model(ModelType.CLASSIFICATION)
        
        self.assertIsInstance(analysis_model, str)
        self.assertIsInstance(generation_model, str)
        self.assertIsInstance(classification_model, str)
    
    @patch('apps.ai_integration.ai_providers.requests.Session.post')
    def test_claude_api_request(self, mock_post):
        """Test Claude API request handling"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'text': 'Test AI response'}],
            'usage': {'output_tokens': 10}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        provider = ClaudeProvider(api_key="test-key")
        request = AIRequest(
            prompt="Test prompt",
            system_prompt="Test system prompt",
            model_type=ModelType.ANALYSIS
        )
        
        response = provider.generate_response(request)
        
        self.assertIsInstance(response, AIResponse)
        self.assertEqual(response.content, 'Test AI response')
        self.assertEqual(response.provider, AIProvider.CLAUDE)
        self.assertEqual(response.tokens_used, 10)
        mock_post.assert_called_once()


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
})
class TestAIManager(TestCase):
    """Test AI Manager functionality"""
    
    @override_settings(
        ANTHROPIC_API_KEY="test-claude-key",
        GOOGLE_AI_API_KEY="test-gemini-key",
        OPENROUTER_API_KEY="test-openrouter-key"
    )
    def test_ai_manager_initialization(self):
        """Test AI manager initializes with configured providers"""
        manager = AIManager()
        available_providers = manager.get_available_providers()
        
        # Should have all three providers
        self.assertIn(AIProvider.CLAUDE, available_providers)
        self.assertIn(AIProvider.GEMINI, available_providers)
        self.assertIn(AIProvider.OPENROUTER, available_providers)
    
    @override_settings(ANTHROPIC_API_KEY=None, GOOGLE_AI_API_KEY=None, OPENROUTER_API_KEY=None)
    def test_ai_manager_no_providers(self):
        """Test AI manager with no configured providers"""
        manager = AIManager()
        available_providers = manager.get_available_providers()
        
        self.assertEqual(len(available_providers), 0)
    
    @patch.object(ClaudeProvider, 'generate_response')
    def test_ai_manager_fallback(self, mock_claude):
        """Test AI manager fallback functionality"""
        # Mock Claude provider to fail
        mock_claude.side_effect = Exception("Claude API error")
        
        # Mock successful Gemini response
        with patch.object(GeminiProvider, 'generate_response') as mock_gemini:
            mock_gemini.return_value = AIResponse(
                content="Fallback response",
                provider=AIProvider.GEMINI,
                model="gemini-1.5-flash"
            )
            
            manager = AIManager()
            request = AIRequest(prompt="Test prompt")
            
            # Should fall back to Gemini
            response = manager.generate_response(
                request, 
                preferred_provider=AIProvider.CLAUDE,
                fallback=True
            )
            
            self.assertEqual(response.content, "Fallback response")
            self.assertEqual(response.provider, AIProvider.GEMINI)


class TestAIServices(TestCase):
    """Test AI service implementations"""
    
    def setUp(self):
        """Set up test data"""
        self.agency = Agency.objects.create(name="Department of Defense", abbreviation="DOD")
        self.naics = NAICSCode.objects.create(code="541330", title="Engineering Services")
        
        self.opportunity = Opportunity.objects.create(
            title="Test Engineering Contract",
            solicitation_number="TEST-2024-001",
            agency=self.agency,
            description="Test opportunity for engineering services",
            posted_date=timezone.now(),
            source_url="https://test.sam.gov/test"
        )
        self.opportunity.naics_codes.add(self.naics)
    
    @patch('apps.ai_integration.services.ai_manager.generate_response')
    def test_opportunity_analysis_service(self, mock_ai_response):
        """Test opportunity analysis service"""
        # Mock AI response
        mock_ai_response.return_value = AIResponse(
            content="""
            Executive Summary: This is a test engineering contract with good potential.
            
            Technical Requirements:
            • Software development
            • System integration
            • Testing and validation
            
            Business Opportunity: High value contract with repeat potential.
            Risk Assessment: Low to medium risk project.
            Compliance: Standard federal requirements apply.
            Competitive Landscape: Moderate competition expected.
            Recommendation: Pursue this opportunity.
            Confidence Score: 0.85
            Keywords: engineering, software, integration
            """,
            provider=AIProvider.CLAUDE,
            model="claude-3-5-sonnet"
        )
        
        service = OpportunityAnalysisService()
        opportunity_data = {
            'title': self.opportunity.title,
            'solicitation_number': self.opportunity.solicitation_number,
            'agency_name': self.agency.name,
            'description': self.opportunity.description,
            'naics_codes': ['541330']
        }
        
        analysis = service.analyze_opportunity(opportunity_data)
        
        self.assertIsNotNone(analysis)
        self.assertIn("test engineering contract", analysis.executive_summary.lower())
        self.assertGreater(len(analysis.technical_requirements), 0)
        self.assertIn("software", analysis.technical_requirements[0].lower())
        mock_ai_response.assert_called_once()
    
    @patch('apps.ai_integration.services.ai_manager.generate_response')
    def test_compliance_service(self, mock_ai_response):
        """Test compliance checking service"""
        # Mock compliance response
        mock_ai_response.return_value = AIResponse(
            content="""
            Overall Status: COMPLIANT
            
            The opportunity meets all basic federal acquisition requirements.
            Set-aside requirements are clearly defined.
            Technical specifications are reasonable.
            
            Confidence Score: 0.90
            """,
            provider=AIProvider.CLAUDE,
            model="claude-3-5-haiku"
        )
        
        service = ComplianceService()
        opportunity_data = {
            'solicitation_number': self.opportunity.solicitation_number,
            'agency_name': self.agency.name,
            'description': self.opportunity.description,
            'set_aside_type': 'Full and Open',
            'opportunity_type': 'Contract'
        }
        
        compliance_check = service.check_compliance(opportunity_data)
        
        self.assertIsNotNone(compliance_check)
        self.assertEqual(compliance_check.overall_status, 'COMPLIANT')
        self.assertGreaterEqual(compliance_check.confidence_score, 0.0)
        mock_ai_response.assert_called_once()
    
    @patch('apps.ai_integration.services.ai_manager.generate_response')
    def test_content_generation_service(self, mock_ai_response):
        """Test content generation service"""
        # Mock content generation response
        mock_ai_response.return_value = AIResponse(
            content="""
            PROPOSAL OUTLINE
            
            1. Executive Summary
               - Project overview and value proposition
               - Key differentiators
            
            2. Technical Approach
               - System architecture
               - Development methodology
               - Quality assurance
            
            3. Management Plan
               - Project management structure
               - Key personnel
               - Communication plan
            
            4. Past Performance
               - Relevant project experience
               - Client references
            
            5. Pricing Strategy
               - Cost breakdown
               - Value engineering opportunities
            """,
            provider=AIProvider.CLAUDE,
            model="claude-3-5-sonnet"
        )
        
        from .services import OpportunityAnalysis
        analysis = OpportunityAnalysis(
            executive_summary="Test analysis summary",
            technical_requirements=["Software development", "Testing"],
            business_opportunity="High value opportunity",
            risk_assessment="Low risk",
            compliance_notes="Standard requirements",
            competitive_landscape="Moderate competition",
            recommendation="Pursue",
            confidence_score=0.8,
            keywords=["engineering", "software"]
        )
        
        service = ContentGenerationService()
        opportunity_data = {
            'title': self.opportunity.title,
            'agency_name': self.agency.name,
            'description': self.opportunity.description
        }
        
        outline = service.generate_proposal_outline(opportunity_data, analysis)
        
        self.assertIsNotNone(outline)
        self.assertIn("PROPOSAL OUTLINE", outline)
        self.assertIn("Executive Summary", outline)
        mock_ai_response.assert_called_once()


class TestAITasks(TestCase):
    """Test AI task management"""
    
    def setUp(self):
        """Set up test data"""
        self.agency = Agency.objects.create(name="Department of Defense", abbreviation="DOD")
        self.opportunity = Opportunity.objects.create(
            title="Test Contract",
            solicitation_number="TEST-2024-002",
            agency=self.agency,
            description="Test opportunity",
            posted_date=timezone.now(),
            source_url="https://test.sam.gov/test"
        )
    
    def test_ai_task_creation(self):
        """Test AI task model creation"""
        task = AITask.objects.create(
            task_type='analyze_opportunity',
            opportunity=self.opportunity,
            input_data={'test': 'data'},
            ai_provider='claude',
            model_used='claude-3-5-sonnet'
        )
        
        self.assertEqual(task.task_type, 'analyze_opportunity')
        self.assertEqual(task.opportunity, self.opportunity)
        self.assertEqual(task.ai_provider, 'claude')
        self.assertEqual(task.status, 'pending')
    
    def test_ai_task_update(self):
        """Test AI task updates"""
        task = AITask.objects.create(
            task_type='compliance_check',
            opportunity=self.opportunity,
            input_data={'test': 'data'},
            ai_provider='gemini'
        )
        
        # Update task with results
        task.status = 'completed'
        task.output_data = {'result': 'COMPLIANT'}
        task.confidence_score = 0.95
        task.tokens_used = 150
        task.processing_time = 2.5
        task.save()
        
        updated_task = AITask.objects.get(id=task.id)
        self.assertEqual(updated_task.status, 'completed')
        self.assertEqual(updated_task.confidence_score, 0.95)
        self.assertEqual(updated_task.tokens_used, 150)


class TestAIIntegration(TestCase):
    """Integration tests for AI functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.agency = Agency.objects.create(name="Test Agency", abbreviation="TA")
        self.naics = NAICSCode.objects.create(code="541330", title="Engineering Services")
        
        self.opportunity = Opportunity.objects.create(
            title="Test AI Integration",
            solicitation_number="TEST-AI-2024-001",
            agency=self.agency,
            description="Test opportunity for AI integration validation",
            posted_date=timezone.now(),
            source_url="https://test.sam.gov/ai-test"
        )
        self.opportunity.naics_codes.add(self.naics)
    
    @patch('apps.ai_integration.services.ai_manager.generate_response')
    def test_end_to_end_ai_analysis(self, mock_ai):
        """Test complete AI analysis workflow"""
        # Mock AI responses for different calls
        mock_ai.side_effect = [
            # Analysis response
            AIResponse(
                content="Executive Summary: Excellent opportunity for our engineering team.",
                provider=AIProvider.CLAUDE,
                model="claude-3-5-sonnet"
            ),
            # Compliance response  
            AIResponse(
                content="Overall Status: COMPLIANT. All requirements met.",
                provider=AIProvider.CLAUDE,
                model="claude-3-5-haiku"
            ),
            # Content generation response
            AIResponse(
                content="PROPOSAL OUTLINE: 1. Executive Summary 2. Technical Approach",
                provider=AIProvider.CLAUDE,
                model="claude-3-5-sonnet"
            )
        ]
        
        # Test analysis service
        analysis_service = OpportunityAnalysisService()
        opportunity_data = {
            'title': self.opportunity.title,
            'solicitation_number': self.opportunity.solicitation_number,
            'agency_name': self.agency.name,
            'description': self.opportunity.description
        }
        
        analysis = analysis_service.analyze_opportunity(opportunity_data)
        self.assertIsNotNone(analysis)
        
        # Test compliance service
        compliance_service = ComplianceService()
        compliance_check = compliance_service.check_compliance(opportunity_data)
        self.assertIsNotNone(compliance_check)
        
        # Test content generation
        content_service = ContentGenerationService()
        proposal_outline = content_service.generate_proposal_outline(opportunity_data, analysis)
        self.assertIsNotNone(proposal_outline)
        
        # Verify all AI calls were made
        self.assertEqual(mock_ai.call_count, 3)
    
    def test_opportunity_ai_data_storage(self):
        """Test storing AI analysis data in opportunity model"""
        # Add AI analysis data
        ai_analysis_data = {
            'executive_summary': 'Test summary',
            'technical_requirements': ['Requirement 1', 'Requirement 2'],
            'confidence_score': 0.85,
            'analyzed_at': timezone.now().isoformat()
        }
        
        self.opportunity.ai_analysis_data = ai_analysis_data
        self.opportunity.ai_analysis_complete = True
        self.opportunity.save()
        
        # Retrieve and verify
        updated_opportunity = Opportunity.objects.get(id=self.opportunity.id)
        self.assertTrue(updated_opportunity.ai_analysis_complete)
        self.assertEqual(
            updated_opportunity.ai_analysis_data['executive_summary'],
            'Test summary'
        )
        self.assertEqual(
            updated_opportunity.ai_analysis_data['confidence_score'],
            0.85
        )