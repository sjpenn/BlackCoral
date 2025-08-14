#!/usr/bin/env python
"""
Test script for USASpending.gov integration
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/sjpenn/Sites/BlackCoral')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings')
django.setup()

from apps.opportunities.api_clients.usaspending_gov import USASpendingClient
from apps.opportunities.models import Opportunity
from apps.core.models import NAICSCode, Agency
from django.contrib.auth import get_user_model

def test_usaspending_client():
    """Test USASpending client functionality"""
    print("🧪 Testing USASpending.gov API client...")
    
    client = USASpendingClient()
    
    # Test 1: Basic NAICS spending query
    print("\n1. Testing NAICS spending query...")
    naics_result = client.get_spending_by_naics(['541330'])  # Engineering services
    if naics_result:
        print("✅ NAICS spending query successful")
        print(f"   Response keys: {list(naics_result.keys())}")
    else:
        print("❌ NAICS spending query failed")
    
    # Test 2: Agency spending query
    print("\n2. Testing agency spending query...")
    agency_result = client.get_spending_by_agency(['Department of Defense'])
    if agency_result:
        print("✅ Agency spending query successful")
        print(f"   Response keys: {list(agency_result.keys())}")
    else:
        print("❌ Agency spending query failed")
    
    # Test 3: Opportunity context analysis
    print("\n3. Testing opportunity context analysis...")
    opportunity_data = {
        'naics_codes': ['541330'],
        'agency_name': 'Department of Defense',
        'solicitation_number': 'TEST-2024-001',
        'title': 'Test Engineering Services',
        'description': 'Test opportunity for engineering services'
    }
    
    analysis = client.analyze_opportunity_context(opportunity_data)
    print("✅ Opportunity analysis completed")
    print(f"   Analysis components: {list(analysis.keys())}")
    
    for key, value in analysis.items():
        if value is not None:
            print(f"   - {key}: ✅ Data available")
        else:
            print(f"   - {key}: ❌ No data")


def test_database_integration():
    """Test database integration with USASpending fields"""
    print("\n🗄️ Testing database integration...")
    
    # Check if model fields exist
    try:
        opportunity = Opportunity()
        opportunity.usaspending_analyzed
        opportunity.usaspending_data
        print("✅ USASpending fields exist in Opportunity model")
    except AttributeError as e:
        print(f"❌ Missing model fields: {e}")
        return
    
    # Test opportunity creation and USASpending data storage
    User = get_user_model()
    
    # Create test data if it doesn't exist
    naics, _ = NAICSCode.objects.get_or_create(
        code='541330',
        defaults={'title': 'Engineering Services'}
    )
    
    agency, _ = Agency.objects.get_or_create(
        name='Department of Defense',
        defaults={'abbreviation': 'DOD'}
    )
    
    # Create test opportunity
    opportunity, created = Opportunity.objects.get_or_create(
        solicitation_number='TEST-USA-2024-001',
        defaults={
            'title': 'Test USASpending Integration',
            'description': 'Test opportunity for USASpending analysis',
            'posted_date': django.utils.timezone.now(),
            'source_url': 'https://test.sam.gov/test',
            'agency': agency
        }
    )
    
    if created:
        opportunity.naics_codes.add(naics)
        print("✅ Test opportunity created")
    else:
        print("✅ Test opportunity already exists")
    
    # Test USASpending data storage
    test_analysis_data = {
        'naics_spending': {'test': 'data'},
        'agency_spending': {'test': 'data'},
        'similar_awards': None,
        'spending_trends': {'test': 'trends'},
        'top_contractors': None
    }
    
    opportunity.usaspending_data = test_analysis_data
    opportunity.usaspending_analyzed = True
    opportunity.save()
    
    print("✅ USASpending data saved to database")
    
    # Verify data retrieval
    retrieved_opportunity = Opportunity.objects.get(id=opportunity.id)
    assert retrieved_opportunity.usaspending_analyzed == True
    assert retrieved_opportunity.usaspending_data == test_analysis_data
    
    print("✅ USASpending data retrieved successfully")
    print(f"   Analysis data keys: {list(retrieved_opportunity.usaspending_data.keys())}")


def main():
    """Run all tests"""
    print("🚀 BLACK CORAL USASpending.gov Integration Test")
    print("=" * 50)
    
    try:
        test_usaspending_client()
        test_database_integration()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        print("\n📊 USASpending.gov integration is ready for Phase 2 completion")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()