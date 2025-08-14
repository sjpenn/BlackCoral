#!/usr/bin/env python
"""
Test AI Enhancement Features
"""
import os
import sys
import django

# Setup Django
sys.path.append('/Users/sjpenn/Sites/BlackCoral')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings')
django.setup()

from apps.collaboration.ai_services import section_ai_enhancer

def test_ai_features():
    print("Testing AI Enhancement Features...")
    
    # Test data
    sample_content = """
    <p>Our company provides excellent technical solutions for government agencies. 
    We have experience and can deliver quality results.</p>
    """
    
    section_title = "Technical Approach"
    requirements = "Describe technical methodology with specific examples"
    
    print("\n1. Testing Content Enhancement...")
    try:
        result = section_ai_enhancer.enhance_content(
            content=sample_content,
            section_title=section_title,
            requirements=requirements,
            enhancement_type="improve"
        )
        
        if 'error' in result:
            print(f"   ❌ Enhancement failed: {result['error']}")
        else:
            print(f"   ✅ Enhancement successful")
            print(f"   📝 Result type: {type(result)}")
            if 'enhanced_content' in result:
                print(f"   📄 Enhanced content available: {len(result['enhanced_content'])} characters")
            
    except Exception as e:
        print(f"   ❌ Enhancement error: {str(e)}")
    
    print("\n2. Testing Outline Generation...")
    try:
        result = section_ai_enhancer.generate_outline(
            section_title=section_title,
            requirements=requirements,
            word_count_target=1500
        )
        
        if 'error' in result:
            print(f"   ❌ Outline generation failed: {result['error']}")
        else:
            print(f"   ✅ Outline generation successful")
            if 'outline' in result:
                print(f"   📋 Outline generated")
            
    except Exception as e:
        print(f"   ❌ Outline error: {str(e)}")
    
    print("\n3. Testing Compliance Check...")
    try:
        result = section_ai_enhancer.check_compliance(
            content=sample_content,
            section_title=section_title,
            requirements=requirements
        )
        
        if 'error' in result:
            print(f"   ❌ Compliance check failed: {result['error']}")
        else:
            print(f"   ✅ Compliance check successful")
            if 'compliance_score' in result:
                print(f"   📊 Compliance score: {result['compliance_score']}%")
            
    except Exception as e:
        print(f"   ❌ Compliance error: {str(e)}")
    
    print("\n4. Testing Suggestions...")
    try:
        result = section_ai_enhancer.suggest_improvements(
            content=sample_content,
            section_title=section_title,
            word_count_current=50,
            word_count_target=200
        )
        
        if 'error' in result:
            print(f"   ❌ Suggestions failed: {result['error']}")
        else:
            print(f"   ✅ Suggestions successful")
            if 'suggestions' in result:
                print(f"   💡 Generated {len(result['suggestions'])} suggestions")
            
    except Exception as e:
        print(f"   ❌ Suggestions error: {str(e)}")
    
    print("\nAI Enhancement Features Test Complete!")
    print("\nNote: If AI provider keys are not configured, some features may show 'service unavailable' errors.")
    print("This is expected and the features will work once AI providers are properly configured.")

if __name__ == '__main__':
    test_ai_features()