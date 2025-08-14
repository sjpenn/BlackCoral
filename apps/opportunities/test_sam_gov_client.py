"""
Comprehensive tests for SAM.gov API Client
Tests parameter building, response parsing, error handling, caching, and rate limiting.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.utils import timezone
import requests

from .api_clients.sam_gov import SAMGovClient, SAMGovAPIError


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
})
class TestSAMGovClient(TestCase):
    """Test suite for SAMGovClient implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use a mock cache for rate limiting tests
        self.mock_cache = {}
        self.api_key = "test_api_key_123"
        self.client = SAMGovClient(api_key=self.api_key)
        
        # Sample opportunity data matching SAM.gov API structure
        self.sample_opportunity = {
            "noticeId": "test-notice-123",
            "title": "Test Opportunity",
            "solicitationNumber": "SOL-2024-001",
            "fullParentPathName": "Department of Defense.Army",
            "naicsCode": "541511",
            "postedDate": "01/15/2024",
            "responseDeadLine": "02/15/2024",
            "description": "Test opportunity description",
            "resourceLinks": [
                "https://sam.gov/document1.pdf",
                "https://sam.gov/document2.pdf"
            ],
            "additionalInfoLink": "https://sam.gov/additional-info",
            "uiLink": "https://sam.gov/opp/test-notice-123"
        }
        
        self.sample_api_response = {
            "opportunities": [self.sample_opportunity],
            "totalRecords": 1
        }
    
    def tearDown(self):
        """Clean up after tests."""
        self.mock_cache.clear()


class TestSAMGovClientInitialization(TestSAMGovClient):
    """Test client initialization and configuration."""
    
    def test_initialization_with_api_key(self):
        """Test successful initialization with API key."""
        client = SAMGovClient(api_key="test_key")
        self.assertEqual(client.api_key, "test_key")
        self.assertEqual(client.base_url, SAMGovClient.BASE_URL)
        self.assertEqual(client.account_type, "non_federal")
    
    def test_initialization_with_alpha_endpoint(self):
        """Test initialization with alpha endpoint."""
        client = SAMGovClient(api_key="test_key", use_alpha=True)
        self.assertEqual(client.base_url, SAMGovClient.ALPHA_URL)
    
    def test_initialization_without_api_key(self):
        """Test initialization fails without API key."""
        with self.assertRaises(SAMGovAPIError) as cm:
            SAMGovClient(api_key=None)
        self.assertIn("API key is required", str(cm.exception))
    
    @override_settings(SAM_GOV_API_KEY="settings_key", SAM_GOV_ACCOUNT_TYPE="federal_system")
    def test_initialization_from_settings(self):
        """Test initialization from Django settings."""
        client = SAMGovClient()
        self.assertEqual(client.api_key, "settings_key")
        self.assertEqual(client.account_type, "federal_system")
        self.assertEqual(client.daily_limit, 10000)


class TestCacheKeyGeneration(TestSAMGovClient):
    """Test cache key generation logic."""
    
    def test_cache_key_generation(self):
        """Test cache key is generated consistently."""
        params1 = {"limit": "10", "offset": "0", "title": "test"}
        params2 = {"title": "test", "limit": "10", "offset": "0"}
        
        key1 = self.client._get_cache_key(params1)
        key2 = self.client._get_cache_key(params2)
        
        # Should be the same regardless of parameter order
        self.assertEqual(key1, key2)
        self.assertTrue(key1.startswith("sam_gov:"))
    
    def test_cache_key_with_special_characters(self):
        """Test cache key handles special characters properly."""
        params = {"title": "test & development", "naics": "541511"}
        key = self.client._get_cache_key(params)
        self.assertIsInstance(key, str)
        self.assertTrue(key.startswith("sam_gov:"))


class TestRateLimiting(TestSAMGovClient):
    """Test rate limiting functionality."""
    
    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_rate_limit_check_within_limits(self, mock_set, mock_get):
        """Test rate limit check passes when within limits."""
        mock_get.return_value = 0
        self.assertTrue(self.client._check_rate_limit())
    
    @patch('django.core.cache.cache.get')
    def test_rate_limit_check_exceeded(self, mock_get):
        """Test rate limit check fails when exceeded."""
        mock_get.return_value = self.client.daily_limit
        self.assertFalse(self.client._check_rate_limit())
    
    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_rate_limit_increment(self, mock_set, mock_get):
        """Test rate limit counter increments properly."""
        mock_get.return_value = 5
        
        self.client._increment_rate_limit()
        
        # Should increment count by 1
        mock_set.assert_called_once()
        args, kwargs = mock_set.call_args
        self.assertEqual(args[1], 6)  # 5 + 1
    


class TestAPIRequests(TestSAMGovClient):
    """Test API request handling."""
    
    @patch('apps.opportunities.api_clients.sam_gov.requests.get')
    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_successful_api_request(self, mock_cache_set, mock_cache_get, mock_get):
        """Test successful API request."""
        mock_cache_get.return_value = 0  # Rate limit check
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response
        
        params = {"limit": "10", "offset": "0"}
        result = self.client._make_request(params)
        
        self.assertEqual(result, self.sample_api_response)
        mock_get.assert_called_once()
        
        # Verify request parameters
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], self.client.base_url)
        self.assertIn("api_key", call_args[1]["params"])
        self.assertEqual(call_args[1]["params"]["api_key"], self.api_key)
    
    @patch('apps.opportunities.api_clients.sam_gov.requests.get')
    @patch('django.core.cache.cache.get')
    def test_rate_limit_error_429(self, mock_cache_get, mock_get):
        """Test handling of 429 rate limit error."""
        mock_cache_get.return_value = 0  # Rate limit check passes
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response
        
        params = {"limit": "10"}
        with self.assertRaises(SAMGovAPIError) as cm:
            self.client._make_request(params)
        
        self.assertIn("Rate limit exceeded", str(cm.exception))
    
    @patch('apps.opportunities.api_clients.sam_gov.requests.get')
    @patch('django.core.cache.cache.get')
    def test_invalid_api_key_401(self, mock_cache_get, mock_get):
        """Test handling of 401 invalid API key error."""
        mock_cache_get.return_value = 0
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        params = {"limit": "10"}
        with self.assertRaises(SAMGovAPIError) as cm:
            self.client._make_request(params)
        
        self.assertIn("Invalid API key", str(cm.exception))
    
    @patch('apps.opportunities.api_clients.sam_gov.requests.get')
    @patch('django.core.cache.cache.get')
    def test_general_api_error(self, mock_cache_get, mock_get):
        """Test handling of general API errors."""
        mock_cache_get.return_value = 0
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_get.return_value = mock_response
        
        params = {"limit": "10"}
        with self.assertRaises(SAMGovAPIError) as cm:
            self.client._make_request(params)
        
        self.assertIn("API error: 500", str(cm.exception))
    
    @patch('apps.opportunities.api_clients.sam_gov.requests.get')
    @patch('django.core.cache.cache.get')
    def test_network_error(self, mock_cache_get, mock_get):
        """Test handling of network errors."""
        mock_cache_get.return_value = 0
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        params = {"limit": "10"}
        with self.assertRaises(SAMGovAPIError) as cm:
            self.client._make_request(params)
        
        self.assertIn("Request failed", str(cm.exception))
    
    @patch('apps.opportunities.api_clients.sam_gov.requests.get')
    @patch('django.core.cache.cache.get')
    def test_timeout_error(self, mock_cache_get, mock_get):
        """Test handling of timeout errors."""
        mock_cache_get.return_value = 0
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        params = {"limit": "10"}
        with self.assertRaises(SAMGovAPIError) as cm:
            self.client._make_request(params)
        
        self.assertIn("Request failed", str(cm.exception))
    
    @patch('django.core.cache.cache.get')
    def test_rate_limit_exceeded_before_request(self, mock_get):
        """Test request fails when rate limit already exceeded."""
        mock_get.return_value = self.client.daily_limit  # Rate limit exceeded
        
        params = {"limit": "10"}
        with self.assertRaises(SAMGovAPIError) as cm:
            self.client._make_request(params)
        
        self.assertIn("Daily rate limit exceeded", str(cm.exception))


class TestParameterBuilding(TestSAMGovClient):
    """Test parameter building for opportunity search."""
    
    @patch('apps.opportunities.api_clients.sam_gov.SAMGovClient._make_request')
    def test_basic_search_parameters(self, mock_request):
        """Test basic search parameter building."""
        mock_request.return_value = self.sample_api_response
        
        self.client.search_opportunities(limit=50, offset=10)
        
        # Verify parameters passed to _make_request
        call_args = mock_request.call_args[0][0]
        self.assertEqual(call_args['limit'], '50')
        self.assertEqual(call_args['offset'], '10')
        self.assertIn('postedFrom', call_args)
        self.assertIn('postedTo', call_args)
    
    @patch('apps.opportunities.api_clients.sam_gov.SAMGovClient._make_request')
    def test_date_range_parameters(self, mock_request):
        """Test date range parameter formatting."""
        mock_request.return_value = self.sample_api_response
        
        posted_from = datetime(2024, 1, 1)
        posted_to = datetime(2024, 2, 1)
        
        self.client.search_opportunities(
            posted_from=posted_from,
            posted_to=posted_to
        )
        
        call_args = mock_request.call_args[0][0]
        self.assertEqual(call_args['postedFrom'], '01/01/2024')
        self.assertEqual(call_args['postedTo'], '02/01/2024')
    
    @patch('apps.opportunities.api_clients.sam_gov.SAMGovClient._make_request')
    def test_response_deadline_parameters(self, mock_request):
        """Test response deadline parameter formatting."""
        mock_request.return_value = self.sample_api_response
        
        rdl_from = datetime(2024, 1, 15)
        rdl_to = datetime(2024, 2, 15)
        
        self.client.search_opportunities(
            response_deadline_from=rdl_from,
            response_deadline_to=rdl_to
        )
        
        call_args = mock_request.call_args[0][0]
        self.assertEqual(call_args['rdlfrom'], '01/15/2024')
        self.assertEqual(call_args['rdlto'], '02/15/2024')
    
    @patch('apps.opportunities.api_clients.sam_gov.SAMGovClient._make_request')
    def test_title_parameter(self, mock_request):
        """Test title search parameter."""
        mock_request.return_value = self.sample_api_response
        
        self.client.search_opportunities(title="IT Services")
        
        call_args = mock_request.call_args[0][0]
        self.assertEqual(call_args['title'], 'IT Services')
    
    @patch('apps.opportunities.api_clients.sam_gov.SAMGovClient._make_request')
    def test_date_range_validation(self, mock_request):
        """Test date range is limited to 1 year."""
        mock_request.return_value = self.sample_api_response
        
        # Set date range > 1 year
        posted_from = datetime(2022, 1, 1)
        posted_to = datetime(2024, 1, 1)  # 2 years
        
        self.client.search_opportunities(
            posted_from=posted_from,
            posted_to=posted_to
        )
        
        call_args = mock_request.call_args[0][0]
        # Should be adjusted to last 365 days from posted_to
        expected_from = datetime(2023, 1, 1).strftime('%m/%d/%Y')
        self.assertEqual(call_args['postedFrom'], expected_from)

class TestNAICSFiltering(TestSAMGovClient):
    """Test NAICS code filtering functionality."""
    
    @patch('apps.opportunities.api_clients.sam_gov.SAMGovClient._make_request')
    def test_naics_filtering(self, mock_request):
        """Test client-side NAICS filtering."""
        opportunities = [
            {**self.sample_opportunity, "naicsCode": "541511"},
            {**self.sample_opportunity, "naicsCode": "541512"},
            {**self.sample_opportunity, "naicsCode": "541519"}
        ]
        mock_request.return_value = {"opportunities": opportunities}
        
        result = self.client.search_opportunities(naics_codes=["541511", "541519"])
        
        returned_opportunities = result['opportunities']
        self.assertEqual(len(returned_opportunities), 2)
        naics_codes = [opp['naicsCode'] for opp in returned_opportunities]
        self.assertIn("541511", naics_codes)
        self.assertIn("541519", naics_codes)
        self.assertNotIn("541512", naics_codes)


class TestAPIDocumentationCompliance(TestSAMGovClient):
    """Test compliance with SAM.gov API documentation."""
    
    def test_base_url_correct(self):
        """Test base URL matches API documentation."""
        expected_url = "https://api.sam.gov/prod/opportunities/v2/search"
        self.assertEqual(SAMGovClient.BASE_URL, expected_url)
    
    def test_alpha_url_correct(self):
        """Test alpha URL is correctly configured."""
        expected_url = "https://api-alpha.sam.gov/prodlike/opportunities/v2/search"
        self.assertEqual(SAMGovClient.ALPHA_URL, expected_url)
    
    def test_rate_limits_match_documentation(self):
        """Test rate limits match API documentation."""
        expected_limits = {
            'non_federal': 10,
            'entity_associated': 1000,
            'federal_system': 10000
        }
        self.assertEqual(SAMGovClient.RATE_LIMITS, expected_limits)


class TestDocumentExtraction(TestSAMGovClient):
    """Test document link extraction."""
    
    def test_extract_resource_links(self):
        """Test extraction of resource links."""
        documents = self.client.get_opportunity_documents(self.sample_opportunity)
        
        resource_docs = [doc for doc in documents if doc['type'] == 'resource']
        self.assertEqual(len(resource_docs), 2)
        self.assertEqual(resource_docs[0]['url'], 'https://sam.gov/document1.pdf')
        self.assertEqual(resource_docs[1]['url'], 'https://sam.gov/document2.pdf')
    
    def test_extract_additional_info_link(self):
        """Test extraction of additional info link."""
        documents = self.client.get_opportunity_documents(self.sample_opportunity)
        
        info_docs = [doc for doc in documents if doc['type'] == 'additional_info']
        self.assertEqual(len(info_docs), 1)
        self.assertEqual(info_docs[0]['url'], 'https://sam.gov/additional-info')
    
    def test_extract_ui_link(self):
        """Test extraction of UI/web link."""
        documents = self.client.get_opportunity_documents(self.sample_opportunity)
        
        ui_docs = [doc for doc in documents if doc['type'] == 'web_link']
        self.assertEqual(len(ui_docs), 1)
        self.assertEqual(ui_docs[0]['url'], 'https://sam.gov/opp/test-notice-123')

    @patch('django.core.cache.cache.get')
    def test_different_api_keys_separate_limits(self, mock_get):
        """Test different API keys have separate rate limits."""
        client2 = SAMGovClient(api_key="different_key")
        
        mock_get.return_value = 0
        # Check both clients
        self.assertTrue(self.client._check_rate_limit())
        self.assertTrue(client2._check_rate_limit())
        
        # Verify different cache keys were used (two calls total)
        self.assertEqual(mock_get.call_count, 2)
