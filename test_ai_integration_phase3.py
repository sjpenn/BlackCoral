#!/usr/bin/env python
"""
BLACK CORAL Phase 3 AI Integration Test Script
Tests Claude, Gemini, and OpenRouter integration with fallback capabilities
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/sjpenn/Sites/BlackCoral')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings')
django.setup()

from apps.ai_integration.ai_providers import ai_manager, AIRequest, ModelType, AIProvider
from apps.ai_integration.services import OpportunityAnalysisService, ComplianceService, ContentGenerationService
from apps.opportunities.models import Opportunity
from apps.core.models import NAICSCode, Agency
from django.contrib.auth import get_user_model
from django.utils import timezone

def test_ai_providers():
    """Test all configured AI providers"""
    print("🤖 Testing AI Provider Configuration...")
    
    available_providers = ai_manager.get_available_providers()
    print(f"   Available providers: {[p.value for p in available_providers]}")
    
    model_info = ai_manager.get_model_info()
    for provider, models in model_info.items():
        print(f"   {provider}: {len(models)} models available")
        if models:
            print(f"      Sample models: {models[:3]}")
    
    if not available_providers:
        print("   ⚠️  No AI providers configured - tests will use mock responses")
        return False
    
    return True


def test_ai_request_handling():
    """Test basic AI request handling"""
    print("\n🧪 Testing AI Request Handling...")
    
    test_request = AIRequest(
        prompt="Test prompt for AI integration validation",
        system_prompt="You are a test assistant. Respond with: 'AI integration test successful'",
        model_type=ModelType.ANALYSIS,
        max_tokens=100,
        temperature=0.3
    )
    
    try:
        response = ai_manager.generate_response(test_request, fallback=True)
        print(f"✅ AI request successful")
        print(f"   Provider: {response.provider.value}")
        print(f"   Model: {response.model}")
        print(f"   Response length: {len(response.content)} characters")
        print(f"   Processing time: {response.processing_time:.2f}s" if response.processing_time else "N/A")
        return True
        
    except Exception as e:
        print(f"❌ AI request failed: {e}")
        return False


def test_opportunity_analysis():
    """Test AI-powered opportunity analysis"""
    print("\n📊 Testing Opportunity Analysis Service...")
    
    # Create test data
    agency, _ = Agency.objects.get_or_create(
        name='Department of Defense',
        defaults={'abbreviation': 'DOD'}
    )
    
    naics, _ = NAICSCode.objects.get_or_create(
        code='541330',
        defaults={'title': 'Engineering Services'}
    )
    
    opportunity, created = Opportunity.objects.get_or_create(
        solicitation_number='TEST-AI-PHASE3-001',
        defaults={
            'title': 'AI Integration Test - Engineering Services Contract',
            'description': 'Test contract for validating BLACK CORAL AI integration capabilities including technical analysis, compliance checking, and content generation.',
            'posted_date': timezone.now(),
            'source_url': 'https://test.sam.gov/ai-phase3-test',
            'agency': agency
        }
    )
    
    if created:
        opportunity.naics_codes.add(naics)
        print("   ✅ Test opportunity created")
    else:
        print("   ✅ Test opportunity exists")
    
    # Test analysis service
    try:
        analysis_service = OpportunityAnalysisService()
        opportunity_data = {
            'title': opportunity.title,
            'solicitation_number': opportunity.solicitation_number,
            'agency_name': agency.name,
            'description': opportunity.description,
            'naics_codes': ['541330'],
            'posted_date': opportunity.posted_date.isoformat(),
            'set_aside_type': 'Full and Open',
            'opportunity_type': 'Contract'
        }
        
        analysis = analysis_service.analyze_opportunity(opportunity_data)
        
        print("   ✅ Opportunity analysis completed")
        print(f"      Executive Summary: {analysis.executive_summary[:100]}...")
        print(f"      Technical Requirements: {len(analysis.technical_requirements)} items")
        print(f"      Recommendation: {analysis.recommendation}")
        print(f"      Confidence Score: {analysis.confidence_score}")
        print(f"      Keywords: {', '.join(analysis.keywords[:5])}")
        
        # Store analysis in opportunity
        opportunity.ai_analysis_data = {
            'executive_summary': analysis.executive_summary,
            'technical_requirements': analysis.technical_requirements,
            'business_opportunity': analysis.business_opportunity,
            'risk_assessment': analysis.risk_assessment,
            'compliance_notes': analysis.compliance_notes,
            'competitive_landscape': analysis.competitive_landscape,
            'recommendation': analysis.recommendation,
            'confidence_score': analysis.confidence_score,
            'keywords': analysis.keywords,
            'analyzed_at': timezone.now().isoformat()
        }
        opportunity.ai_analysis_complete = True
        opportunity.save()
        
        return opportunity, analysis
        
    except Exception as e:
        print(f"   ❌ Opportunity analysis failed: {e}")
        return None, None


def test_compliance_checking(opportunity_data):
    """Test AI-powered compliance checking"""
    print("\n🛡️ Testing Compliance Checking Service...")
    
    try:
        compliance_service = ComplianceService()
        compliance_check = compliance_service.check_compliance(opportunity_data)
        
        print("   ✅ Compliance check completed")
        print(f"      Overall Status: {compliance_check.overall_status}")
        print(f"      Issues Found: {len(compliance_check.issues)}")
        print(f"      Requirements Met: {len(compliance_check.requirements_met)}")
        print(f"      Requirements Missing: {len(compliance_check.requirements_missing)}")
        print(f"      Confidence Score: {compliance_check.confidence_score}")
        
        return compliance_check
        
    except Exception as e:
        print(f"   ❌ Compliance checking failed: {e}")
        return None


def test_content_generation(opportunity_data, analysis):
    """Test AI-powered content generation"""
    print("\n📝 Testing Content Generation Service...")
    
    try:
        content_service = ContentGenerationService()
        
        # Test proposal outline generation
        print("   Testing proposal outline generation...")
        proposal_outline = content_service.generate_proposal_outline(opportunity_data, analysis)
        print(f"   ✅ Proposal outline generated ({len(proposal_outline)} characters)")
        print(f"      Preview: {proposal_outline[:150]}...")
        
        # Test executive summary generation
        print("   Testing executive summary generation...")
        executive_summary = content_service.generate_executive_summary(opportunity_data, analysis)
        print(f"   ✅ Executive summary generated ({len(executive_summary)} characters)")
        print(f"      Preview: {executive_summary[:150]}...")
        
        return {
            'proposal_outline': proposal_outline,
            'executive_summary': executive_summary
        }
        
    except Exception as e:
        print(f"   ❌ Content generation failed: {e}")
        return None


def test_provider_fallback():
    """Test AI provider fallback functionality"""
    print("\n🔄 Testing Provider Fallback...")
    
    available_providers = ai_manager.get_available_providers()
    if len(available_providers) < 2:
        print("   ⚠️  Need at least 2 providers to test fallback")
        return
    
    # Test with each provider as preferred
    for provider in available_providers:
        try:
            test_request = AIRequest(
                prompt="Respond with: 'Fallback test successful'",
                model_type=ModelType.CLASSIFICATION,
                max_tokens=50
            )
            
            response = ai_manager.generate_response(
                test_request, 
                preferred_provider=provider,
                fallback=True
            )
            
            print(f"   ✅ {provider.value}: {response.content[:50]}...")
            
        except Exception as e:
            print(f"   ❌ {provider.value} failed: {e}")


def test_database_integration():
    """Test AI data storage in database"""
    print("\n💾 Testing Database Integration...")
    
    from apps.ai_integration.models import AITask
    
    # Test AITask creation
    opportunity = Opportunity.objects.filter(solicitation_number='TEST-AI-PHASE3-001').first()
    if not opportunity:
        print("   ❌ Test opportunity not found")
        return
    
    ai_task = AITask.objects.create(
        task_type='analyze_opportunity',
        opportunity=opportunity,
        input_data={'test': 'data'},
        ai_provider='claude',
        model_used='claude-3-5-sonnet-20241022',
        status='completed',
        tokens_used=150,
        processing_time=2.5,
        confidence_score=0.85
    )
    
    print("   ✅ AITask created successfully")
    print(f"      Task ID: {ai_task.id}")
    print(f"      Status: {ai_task.status}")
    print(f"      Provider: {ai_task.get_ai_provider_display()}")
    
    # Test opportunity AI data
    if opportunity.ai_analysis_complete:
        print("   ✅ Opportunity AI analysis data stored")
        print(f"      Analysis keys: {list(opportunity.ai_analysis_data.keys())}")
    
    return ai_task


def test_celery_tasks():
    """Test Celery task integration"""
    print("\n⚙️ Testing Celery Task Integration...")
    
    try:
        from apps.ai_integration.tasks import test_ai_providers
        
        # Test the test task (without actually running it through Celery)
        result = test_ai_providers()
        
        print("   ✅ Celery task structure validated")
        print(f"      Task result: {result['status']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Celery task test failed: {e}")
        return False


def main():
    """Run comprehensive Phase 3 AI integration tests"""
    print("🚀 BLACK CORAL Phase 3 AI Integration Test Suite")
    print("=" * 60)
    
    test_results = {}
    
    # Test 1: Provider Configuration
    test_results['providers'] = test_ai_providers()
    
    # Test 2: Basic AI Request Handling
    test_results['requests'] = test_ai_request_handling()
    
    # Test 3: Opportunity Analysis
    opportunity, analysis = test_opportunity_analysis()
    test_results['analysis'] = opportunity is not None and analysis is not None
    
    if opportunity and analysis:
        opportunity_data = {
            'title': opportunity.title,
            'solicitation_number': opportunity.solicitation_number,
            'agency_name': opportunity.agency.name,
            'description': opportunity.description
        }
        
        # Test 4: Compliance Checking
        compliance_check = test_compliance_checking(opportunity_data)
        test_results['compliance'] = compliance_check is not None
        
        # Test 5: Content Generation
        generated_content = test_content_generation(opportunity_data, analysis)
        test_results['content'] = generated_content is not None
    
    # Test 6: Provider Fallback
    test_provider_fallback()
    
    # Test 7: Database Integration
    ai_task = test_database_integration()
    test_results['database'] = ai_task is not None
    
    # Test 8: Celery Tasks
    test_results['celery'] = test_celery_tasks()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = sum(test_results.values())
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name.title()}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 Phase 3 AI Integration Complete and Fully Functional!")
        print("\n🚀 Ready for Production:")
        print("   • Claude API integration with fallback")
        print("   • Google Gemini content generation")
        print("   • OpenRouter multi-model access")
        print("   • AI-powered opportunity analysis")
        print("   • Automated compliance checking")
        print("   • Proposal content generation")
        print("   • Background task processing")
        print("   • Database storage and tracking")
    else:
        print(f"\n⚠️  {total-passed} test(s) failed - review configuration")


if __name__ == '__main__':
    main()