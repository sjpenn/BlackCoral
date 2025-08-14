"""
Tests for USASpending.gov API client
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache
from apps.opportunities.api_clients.usaspending_gov import USASpendingClient, get_usaspending_client


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
})
class TestUSASpendingClient(TestCase):
    """Test suite for USASpending.gov API client"""
    
    def setUp(self):
        """Set up test client"""
        self.client = USASpendingClient()
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    @patch('apps.opportunities.api_clients.usaspending_gov.requests.Session.post')
    def test_make_request_success(self, mock_post):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': ['test_data']}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.client._make_request('/test', {'test': 'data'})
        
        self.assertEqual(result, {'results': ['test_data']})
        mock_post.assert_called_once()
    
    @patch('apps.opportunities.api_clients.usaspending_gov.requests.Session.post')
    def test_make_request_with_caching(self, mock_post):
        """Test API request caching (dummy cache so no actual caching)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': ['cached_data']}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # First request
        result1 = self.client._make_request('/test', {'test': 'data'})
        
        # Second request (no actual caching with dummy cache)
        result2 = self.client._make_request('/test', {'test': 'data'})
        
        self.assertEqual(result1, result2)
        # With dummy cache, should call API twice
        self.assertEqual(mock_post.call_count, 2)
    
    @patch('apps.opportunities.api_clients.usaspending_gov.requests.Session.post')
    def test_make_request_failure(self, mock_post):
        """Test API request failure handling"""
        mock_post.side_effect = Exception("API Error")
        
        result = self.client._make_request('/test', {'test': 'data'})
        
        self.assertIsNone(result)
    
    @patch.object(USASpendingClient, '_make_request')
    def test_get_spending_by_naics(self, mock_request):
        """Test NAICS spending data retrieval"""
        mock_request.return_value = {
            'results': [
                {
                    'naics': '541330',
                    'amount': 1000000,
                    'description': 'Engineering Services'
                }
            ]
        }
        
        result = self.client.get_spending_by_naics(['541330'], [2023])
        
        self.assertIsNotNone(result)
        mock_request.assert_called_once()
        
        # Verify request data structure
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], '/search/spending_by_category/')
        request_data = call_args[0][1]
        self.assertIn('filters', request_data)
        self.assertEqual(request_data['category'], 'naics')
    
    @patch.object(USASpendingClient, '_make_request')
    def test_get_spending_by_agency(self, mock_request):
        """Test agency spending data retrieval"""
        mock_request.return_value = {
            'results': [
                {
                    'agency': 'Department of Defense',
                    'amount': 50000000
                }
            ]
        }
        
        result = self.client.get_spending_by_agency(['DOD'], [2023])
        
        self.assertIsNotNone(result)
        mock_request.assert_called_once()
        
        call_args = mock_request.call_args
        request_data = call_args[0][1]
        self.assertEqual(request_data['category'], 'awarding_agency')
    
    @patch.object(USASpendingClient, '_make_request')
    def test_get_spending_trends(self, mock_request):
        """Test spending trends over time"""
        mock_request.return_value = {
            'results': [
                {
                    'time_period': '2023-Q1',
                    'amount': 1000000
                },
                {
                    'time_period': '2023-Q2', 
                    'amount': 1200000
                }
            ]
        }
        
        result = self.client.get_spending_trends(['541330'])
        
        self.assertIsNotNone(result)
        mock_request.assert_called_once()
        
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], '/search/spending_over_time/')
    
    @patch.object(USASpendingClient, '_make_request')
    def test_get_top_contractors_by_naics(self, mock_request):
        """Test top contractors retrieval"""
        mock_request.return_value = {
            'results': [
                {
                    'recipient': 'Acme Corp',
                    'amount': 5000000
                },
                {
                    'recipient': 'Beta Industries',
                    'amount': 3000000
                }
            ]
        }
        
        result = self.client.get_top_contractors_by_naics(['541330'], [2023], 5)
        
        self.assertIsNotNone(result)
        mock_request.assert_called_once()
        
        call_args = mock_request.call_args
        request_data = call_args[0][1]
        self.assertEqual(request_data['category'], 'recipient')
        self.assertEqual(request_data['limit'], 5)
    
    @patch.object(USASpendingClient, '_make_request')
    def test_search_awards_by_opportunity(self, mock_request):
        """Test award search functionality"""
        mock_request.return_value = {
            'results': [
                {
                    'award_id': 'ABC123',
                    'recipient': 'Test Corp',
                    'amount': 2000000
                }
            ]
        }
        
        result = self.client.search_awards_by_opportunity(
            solicitation_number='W912DY-24-R-0001',
            agency_name='Department of Defense'
        )
        
        self.assertIsNotNone(result)
        mock_request.assert_called_once()
        
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], '/search/spending_by_award/')
    
    @patch.object(USASpendingClient, '_make_request')
    def test_get_agency_spending_summary(self, mock_request):
        """Test agency spending summary"""
        mock_request.return_value = {
            'results': [
                {
                    'category': 'test',
                    'amount': 1000000
                }
            ]
        }
        
        result = self.client.get_agency_spending_summary('Department of Defense', 2023)
        
        self.assertIsNotNone(result)
        # Should make 2 requests (by_naics and by_recipient)
        self.assertEqual(mock_request.call_count, 2)
        
        self.assertIn('by_naics', result)
        self.assertIn('by_recipient', result)
    
    @patch.object(USASpendingClient, 'get_spending_by_naics')
    @patch.object(USASpendingClient, 'get_spending_trends')
    @patch.object(USASpendingClient, 'get_top_contractors_by_naics')
    @patch.object(USASpendingClient, 'get_agency_spending_summary')
    @patch.object(USASpendingClient, 'search_awards_by_opportunity')
    def test_analyze_opportunity_context(self, mock_search, mock_agency, 
                                       mock_contractors, mock_trends, mock_naics):
        """Test comprehensive opportunity analysis"""
        # Mock all the individual methods
        mock_naics.return_value = {'naics_data': 'test'}
        mock_trends.return_value = {'trends_data': 'test'}
        mock_contractors.return_value = {'contractors_data': 'test'}
        mock_agency.return_value = {'agency_data': 'test'}
        mock_search.return_value = {'awards_data': 'test'}
        
        opportunity_data = {
            'naics_codes': ['541330'],
            'agency_name': 'Department of Defense',
            'solicitation_number': 'W912DY-24-R-0001'
        }
        
        result = self.client.analyze_opportunity_context(opportunity_data)
        
        # Verify all analysis components are present
        self.assertIn('naics_spending', result)
        self.assertIn('agency_spending', result)
        self.assertIn('similar_awards', result)
        self.assertIn('spending_trends', result)
        self.assertIn('top_contractors', result)
        
        # Verify methods were called
        mock_naics.assert_called_once_with(['541330'])
        mock_agency.assert_called_once_with('Department of Defense')
        mock_search.assert_called_once()
    
    def test_analyze_opportunity_context_empty_data(self):
        """Test analysis with empty opportunity data"""
        result = self.client.analyze_opportunity_context({})
        
        # Should return structure with None values
        expected_keys = ['naics_spending', 'agency_spending', 'similar_awards', 
                        'spending_trends', 'top_contractors']
        
        for key in expected_keys:
            self.assertIn(key, result)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        import time
        
        start_time = time.time()
        self.client._rate_limit()
        self.client._rate_limit()
        end_time = time.time()
        
        # Should have some delay
        self.assertGreaterEqual(end_time - start_time, self.client.RATE_LIMIT_DELAY)
    
    def test_get_usaspending_client_function(self):
        """Test convenience function"""
        client = get_usaspending_client()
        self.assertIsInstance(client, USASpendingClient)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
})
class TestUSASpendingIntegration(TestCase):
    """Integration tests for USASpending client (requires network)"""
    
    @pytest.mark.skipif(True, reason="Integration test - requires network")
    def test_real_api_request(self):
        """Test actual API request (disabled by default)"""
        client = USASpendingClient()
        
        # Test with a simple NAICS search
        result = client.get_spending_by_naics(['541330'], [2023])
        
        self.assertIsNotNone(result)
        self.assertIn('results', result)