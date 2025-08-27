"""
SAM.gov Opportunities API Client for BLACK CORAL
Implements opportunity discovery from sam.gov with rate limiting and caching.
"""

import logging
import requests
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, urlparse
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from ..utils.filename_extractor import extract_filenames_from_urls
from apps.ai_integration.services import OpportunityAnalysisService, ComplianceService, ContentGenerationService
from apps.ai_integration.ai_providers import AIProvider
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from apps.authentication.models import User
import json
import hashlib
from datetime import date
from decimal import Decimal

logger = logging.getLogger('blackcoral.sam_gov')


class SAMGovAPIError(Exception):
    """Custom exception for SAM.gov API errors."""
    pass


class SAMGovClient:
    """
    Client for interacting with SAM.gov Opportunities API.
    
    Features:
    - Rate limiting management
    - Response caching
    - Error handling and retry logic
    - NAICS code filtering
    - Agency filtering
    - Description content retrieval from URLs
    - Support for both v2 and v3 API endpoints
    """
    
    BASE_URL = "https://api.sam.gov/prod/opportunities/v2/search"
    BASE_URL_V3 = "https://api.sam.gov/prod/opportunities/v3/search"
    ALPHA_URL = "https://api-alpha.sam.gov/prodlike/opportunities/v2/search"
    ALPHA_URL_V3 = "https://api-alpha.sam.gov/prodlike/opportunities/v3/search"
    
    # Rate limits by account type
    RATE_LIMITS = {
        'non_federal': 10,
        'entity_associated': 1000,
        'federal_system': 10000
    }
    
    def __init__(self, api_key: str = None, use_alpha: bool = False, use_v3: bool = None):
        """
        Initialize SAM.gov API client with API key rotation support.
        
        Args:
            api_key: SAM.gov public API key
            use_alpha: Use alpha/testing endpoint if True
            use_v3: Use v3 API endpoints if True (enhanced description support)
                   If None, uses SAM_GOV_USE_V3_API setting
        """
        self.api_keys = self._get_api_keys()
        self.current_key_index = 0
        
        # Use settings for v3 API if not explicitly specified
        if use_v3 is None:
            use_v3 = getattr(settings, 'SAM_GOV_USE_V3_API', True)
        self.use_v3 = use_v3
        
        # Use settings for alpha endpoint if not explicitly specified
        if use_alpha is None:
            use_alpha = getattr(settings, 'SAM_GOV_USE_ALPHA', False)
        
        # Start with working keys by skipping known disabled ones
        self._skip_known_disabled_keys()
        
        self.api_key = api_key or self._get_next_valid_key()
        
        # Set base URL based on version and environment
        if use_alpha:
            self.base_url = self.ALPHA_URL_V3 if use_v3 else self.ALPHA_URL
        else:
            self.base_url = self.BASE_URL_V3 if use_v3 else self.BASE_URL
            
        self.account_type = getattr(settings, 'SAM_GOV_ACCOUNT_TYPE', 'non_federal')
        self.daily_limit = self.RATE_LIMITS.get(self.account_type, 10)
        
        # Description enhancement settings
        self.enable_description_enhancement = getattr(settings, 'SAM_GOV_ENABLE_DESCRIPTION_ENHANCEMENT', True)
        self.description_fetch_timeout = getattr(settings, 'SAM_GOV_DESCRIPTION_FETCH_TIMEOUT', 10)
        self.description_cache_ttl = getattr(settings, 'SAM_GOV_DESCRIPTION_CACHE_TTL', 3600)
        self.max_description_length = getattr(settings, 'SAM_GOV_MAX_DESCRIPTION_LENGTH', 10000)
        self.min_enhancement_length = getattr(settings, 'SAM_GOV_DESCRIPTION_MIN_ENHANCEMENT_LENGTH', 50)
        
        if not self.api_key:
            raise SAMGovAPIError("No valid SAM.gov API keys available")
    
    def _get_api_keys(self) -> List[str]:
        """Get all available API keys from settings."""
        keys = []
        
        # Primary key
        if hasattr(settings, 'SAM_GOV_API_KEY') and settings.SAM_GOV_API_KEY:
            keys.append(settings.SAM_GOV_API_KEY.strip())
        
        # Additional numbered keys
        for i in range(1, 11):  # Check up to 10 additional keys
            key_name = f'SAM_GOV_API_KEY_{i}'
            if hasattr(settings, key_name):
                key_value = getattr(settings, key_name)
                if key_value and key_value.strip() not in keys:
                    keys.append(key_value.strip())
        
        return keys
    
    def _skip_known_disabled_keys(self):
        """Skip to the first potentially valid API key by avoiding known disabled ones."""
        # These are the known disabled keys from our tests
        disabled_patterns = ['1oTdOm7D', 'hQ2zHWXt', 'VuHISLC', 'yGt0wiU', 'RDdIQSU', 'uO0UjDQ', 'GrqyfUC', 'PXLuTjC', 'raBrlqT', 'ZORdSw5']  # First 8 chars of disabled keys
        
        # New API keys that should work
        valid_patterns = ['2LadXlgG', '2svqGo6G']
        
        for i, key in enumerate(self.api_keys):
            if any(key.startswith(pattern) for pattern in valid_patterns):
                self.current_key_index = i
                logger.info(f"Using API key starting with: {key[:8]}")
                return
            elif not any(key.startswith(pattern) for pattern in disabled_patterns):
                self.current_key_index = i
                break
    
    def _get_next_valid_key(self) -> str:
        """Get the next valid API key from the rotation list."""
        if not self.api_keys:
            return None
        
        # Try each key until we find a working one
        for i in range(len(self.api_keys)):
            key = self.api_keys[self.current_key_index]
            if self._is_key_valid(key):
                return key
            
            # Move to next key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        
        return None
    
    def _is_key_valid(self, api_key: str) -> bool:
        """Check if an API key is valid (not disabled)."""
        cache_key = f"sam_gov_key_disabled:{api_key}"
        return not cache.get(cache_key, False)
    
    def _mark_key_disabled(self, api_key: str):
        """Mark an API key as disabled."""
        cache_key = f"sam_gov_key_disabled:{api_key}"
        cache.set(cache_key, True, 3600)  # Cache for 1 hour
    
    def _get_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate cache key for request parameters."""
        sorted_params = sorted(params.items())
        param_str = urlencode(sorted_params)
        return f"sam_gov:{param_str}"
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we've exceeded our daily rate limit.
        
        Returns:
            True if within limits, False if exceeded
        """
        today = timezone.now().date()
        cache_key = f"sam_gov_requests:{today}:{self.api_key}"
        
        request_count = cache.get(cache_key, 0)
        if request_count >= self.daily_limit:
            logger.warning(f"SAM.gov rate limit exceeded: {request_count}/{self.daily_limit}")
            return False
        
        return True
    
    def _increment_rate_limit(self):
        """Increment the daily request counter."""
        today = timezone.now().date()
        cache_key = f"sam_gov_requests:{today}:{self.api_key}"
        
        request_count = cache.get(cache_key, 0)
        cache.set(cache_key, request_count + 1, 86400)  # Expire after 24 hours
    
    def _make_request(self, params: Dict[str, Any], max_retries: int = 4) -> Dict[str, Any]:
        """
        Make API request with error handling and retry logic.
        
        Args:
            params: Query parameters
            max_retries: Maximum number of retries for 5xx errors
            
        Returns:
            API response data
            
        Raises:
            SAMGovAPIError: On API errors
        """
        # Check rate limit
        if not self._check_rate_limit():
            raise SAMGovAPIError("Daily rate limit exceeded")
        
        # Add API key to params
        params['api_key'] = self.api_key
        
        # Retry configuration
        retry_status_codes = [500, 502, 503, 504]
        base_delay = 0.5  # 500ms
        backoff_factor = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                logger.info("=== HTTP REQUEST DEBUG ===")
                logger.info(f"Making GET request to: {self.base_url}")
                logger.info(f"Attempt {attempt + 1} of {max_retries + 1}")
                logger.info(f"Request timeout: 30 seconds")
                logger.info(f"Request headers: User-Agent: 'BLACK CORAL Government Contracting System', Accept: 'application/json'")
                
                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=30,
                    headers={
                        'User-Agent': 'BLACK CORAL Government Contracting System',
                        'Accept': 'application/json'
                    }
                )
                
                # DEBUG: Log response details
                logger.info("=== HTTP RESPONSE DEBUG ===")
                logger.info(f"Response status code: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")
                logger.info(f"Response content length: {len(response.content)} bytes")
                logger.info(f"Response encoding: {response.encoding}")
                
                # Log response content preview (first 500 chars)
                response_text = response.text
                logger.info(f"Response content preview (first 500 chars): {response_text[:500]}")
                if len(response_text) > 500:
                    logger.info(f"... (truncated, total length: {len(response_text)} chars)")
                
                # Check if we should retry for 5xx errors
                if response.status_code in retry_status_codes and attempt < max_retries:
                    delay = base_delay * (backoff_factor ** attempt)
                    jitter = random.uniform(0, delay * 0.1)  # Add up to 10% jitter
                    total_delay = delay + jitter
                    
                    logger.warning(f"Received {response.status_code} error, retrying in {total_delay:.2f} seconds...")
                    logger.warning(f"Error response: {response_text[:500]}")
                    time.sleep(total_delay)
                    continue
                
                # Check for API key disabled error
                if response.status_code == 403:
                    logger.warning(f"Received 403 Forbidden response")
                    try:
                        error_data = response.json()
                        logger.info(f"403 Error response JSON: {error_data}")
                        if error_data.get('error', {}).get('code') == 'API_KEY_DISABLED':
                            # Mark current key as disabled
                            self._mark_key_disabled(self.api_key)
                            logger.warning(f"API key disabled: {self.api_key[:8]}...")
                            
                            # Try to get next valid key
                            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                            next_key = self._get_next_valid_key()
                            
                            if next_key and next_key != self.api_key:
                                logger.info(f"Switching to next API key: {next_key[:8]}...")
                                self.api_key = next_key
                                # Retry with new key (recursive call, but limited by number of keys)
                                params['api_key'] = self.api_key
                                return self._make_request(params)
                            else:
                                raise SAMGovAPIError("All API keys have been disabled")
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Could not parse 403 response as JSON: {e}")
                        pass  # Not a JSON response or different error structure
            
                # Increment rate limit counter only for successful requests
                if response.status_code == 200:
                    self._increment_rate_limit()
                    logger.info("Request successful, rate limit counter incremented")
                
                # Check for other errors
                if response.status_code == 429:
                    logger.error("Rate limit exceeded (429)")
                    raise SAMGovAPIError("Rate limit exceeded")
                elif response.status_code == 401:
                    logger.error("Invalid API key (401)")
                    raise SAMGovAPIError("Invalid API key")
                elif response.status_code != 200:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    raise SAMGovAPIError(f"API error: {response.status_code} - {response.text}")
                
                # Parse JSON response
                try:
                    json_data = response.json()
                    logger.info("Response successfully parsed as JSON")
                    return json_data
                except ValueError as e:
                    logger.error(f"Failed to parse response as JSON: {e}")
                    logger.error(f"Raw response content: {response.text}")
                    raise SAMGovAPIError(f"Invalid JSON response: {str(e)}")
            
            except requests.exceptions.RequestException as e:
                # For connection errors, retry if we have attempts left
                if attempt < max_retries:
                    delay = base_delay * (backoff_factor ** attempt)
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    logger.warning(f"Request failed: {e}, retrying in {total_delay:.2f} seconds...")
                    time.sleep(total_delay)
                    continue
                else:
                    logger.error(f"SAM.gov API request failed after {max_retries + 1} attempts: {e}")
                    raise SAMGovAPIError(f"Request failed: {str(e)}")
        
        # If we get here, all retries have been exhausted
        logger.error(f"All {max_retries + 1} attempts failed for SAM.gov API request")
        raise SAMGovAPIError("SAM.gov API request failed after all retries")
    
    def search_opportunities(
        self,
        limit: int = 100,
        offset: int = 0,
        posted_from: Optional[datetime] = None,
        posted_to: Optional[datetime] = None,
        naics_codes: Optional[List[str]] = None,
        agencies: Optional[List[str]] = None,
        title: Optional[str] = None,
        response_deadline_from: Optional[datetime] = None,
        response_deadline_to: Optional[datetime] = None,
        cache_timeout: int = 3600
    ) -> Dict[str, Any]:
        """
        Search for opportunities with various filters.
        
        Args:
            limit: Number of records to return
            offset: Pagination offset
            posted_from: Start date for posted opportunities
            posted_to: End date for posted opportunities
            naics_codes: List of NAICS codes to filter (client-side)
            agencies: List of department names to filter
            title: Title search string
            response_deadline_from: Response deadline start date
            response_deadline_to: Response deadline end date
            cache_timeout: Cache timeout in seconds
            
        Returns:
            Dictionary containing opportunities and metadata
        """
        logger.info("=== SAM.gov API Search Debug Information ===")
        
        # Build parameters
        params = {
            'limit': str(limit),
            'offset': str(offset)
        }
        
        # Handle date range (required when using limit)
        if not posted_from:
            posted_from = datetime.now() - timedelta(days=30)
        if not posted_to:
            posted_to = datetime.now()
        
        # Ensure date range is within 1 year
        date_diff = posted_to - posted_from
        if date_diff.days > 365:
            posted_from = posted_to - timedelta(days=365)
            logger.warning("Date range exceeded 1 year, adjusting to last 365 days")
        
        params['postedFrom'] = posted_from.strftime('%m/%d/%Y')
        params['postedTo'] = posted_to.strftime('%m/%d/%Y')
        
        # Add optional filters
        if title:
            params['title'] = title
        
        if response_deadline_from:
            params['rdlfrom'] = response_deadline_from.strftime('%m/%d/%Y')
        
        if response_deadline_to:
            params['rdlto'] = response_deadline_to.strftime('%m/%d/%Y')
        
        # Add server-side NAICS code filtering
        if naics_codes and len(naics_codes) > 0:
            # SAM.gov API supports NAICS code filtering via 'ncode' parameter
            # For multiple NAICS codes, we'll use the first one
            params['ncode'] = naics_codes[0]
        
        # Add server-side agency/department filtering
        if agencies and len(agencies) > 0:
            # SAM.gov API supports organization filtering via 'organizationName' parameter
            # For multiple agencies, we'll use the first one
            params['organizationName'] = agencies[0]
        
        # DEBUG: Log all parameters being sent
        logger.info(f"API Key being used: {self.api_key[:8]}...{self.api_key[-4:]}")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Request Parameters (before adding API key):")
        for key, value in params.items():
            logger.info(f"  {key}: {value}")
        
        # DEBUG: Log filters
        logger.info(f"Server-side filters added to API request:")
        logger.info(f"  NAICS Codes: {naics_codes}")
        logger.info(f"  Agencies: {agencies}")
        
        # Check cache first
        cache_key = self._get_cache_key(params)
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached data for {cache_key}")
            logger.info(f"Cached opportunities count: {len(cached_data.get('opportunities', []))}")
            return cached_data
        
        # Add API key for URL construction logging
        params_with_key = params.copy()
        params_with_key['api_key'] = self.api_key
        
        # DEBUG: Log the exact URL that will be called
        from urllib.parse import urlencode
        query_string = urlencode(params_with_key)
        full_url = f"{self.base_url}?{query_string}"
        logger.info(f"Full URL being called: {full_url}")
        logger.info(f"Query string length: {len(query_string)} characters")
        
        # Remove API key from params again (will be re-added in _make_request)
        del params_with_key['api_key']
        
        # Make API request with fallback on 500 errors
        logger.info("Making API request...")
        try:
            response_data = self._make_request(params)
        except SAMGovAPIError as e:
            # If we get a 500 error after retries, try with reduced parameters
            if "500" in str(e) or "INTERNAL SERVER ERROR" in str(e):
                logger.warning("Got 500 error, trying fallback strategies...")
                
                # First fallback: reduce limit to 10
                if limit > 10:
                    logger.info("Fallback 1: Reducing limit from {} to 10".format(limit))
                    params['limit'] = '10'
                    try:
                        response_data = self._make_request(params)
                    except SAMGovAPIError as e2:
                        # Second fallback: narrow date range to 30 days
                        if posted_to and posted_from:
                            new_from = posted_to - timedelta(days=30)
                            if new_from > posted_from:
                                logger.info("Fallback 2: Narrowing date range to last 30 days")
                                params['postedFrom'] = new_from.strftime('%m/%d/%Y')
                                params['limit'] = '10'  # Keep reduced limit
                                try:
                                    response_data = self._make_request(params)
                                except SAMGovAPIError as e3:
                                    # Third fallback: try v2 endpoint if using v3
                                    if self.use_v3:
                                        logger.info("Fallback 3: Switching from v3 to v2 endpoint")
                                        old_url = self.base_url
                                        self.base_url = self.BASE_URL  # Switch to v2
                                        self.use_v3 = False
                                        try:
                                            response_data = self._make_request(params)
                                            logger.info("v2 endpoint successful - continuing with v2")
                                        except SAMGovAPIError:
                                            # Restore original settings
                                            self.base_url = old_url
                                            self.use_v3 = True
                                            raise e3
                                    else:
                                        raise e3
                            else:
                                # Try v2 endpoint before giving up
                                if self.use_v3:
                                    logger.info("Fallback: Switching from v3 to v2 endpoint")
                                    old_url = self.base_url
                                    self.base_url = self.BASE_URL  # Switch to v2
                                    self.use_v3 = False
                                    try:
                                        response_data = self._make_request(params)
                                        logger.info("v2 endpoint successful - continuing with v2")
                                    except SAMGovAPIError:
                                        # Restore original settings
                                        self.base_url = old_url
                                        self.use_v3 = True
                                        raise e2
                                else:
                                    raise e2
                        else:
                            # Try v2 endpoint before giving up
                            if self.use_v3:
                                logger.info("Fallback: Switching from v3 to v2 endpoint")
                                old_url = self.base_url
                                self.base_url = self.BASE_URL  # Switch to v2
                                self.use_v3 = False
                                try:
                                    response_data = self._make_request(params)
                                    logger.info("v2 endpoint successful - continuing with v2")
                                except SAMGovAPIError:
                                    # Restore original settings
                                    self.base_url = old_url
                                    self.use_v3 = True
                                    raise e2
                            else:
                                raise e2
                else:
                    # If limit is already small, try narrowing date range first
                    if posted_to and posted_from:
                        new_from = posted_to - timedelta(days=30)
                        if new_from > posted_from:
                            logger.info("Fallback: Narrowing date range to last 30 days")
                            params['postedFrom'] = new_from.strftime('%m/%d/%Y')
                            try:
                                response_data = self._make_request(params)
                            except SAMGovAPIError as e2:
                                # Try v2 endpoint
                                if self.use_v3:
                                    logger.info("Fallback: Switching from v3 to v2 endpoint")
                                    old_url = self.base_url
                                    self.base_url = self.BASE_URL  # Switch to v2
                                    self.use_v3 = False
                                    try:
                                        response_data = self._make_request(params)
                                        logger.info("v2 endpoint successful - continuing with v2")
                                    except SAMGovAPIError:
                                        # Restore original settings
                                        self.base_url = old_url
                                        self.use_v3 = True
                                        raise e2
                                else:
                                    raise e2
                        else:
                            # Try v2 endpoint
                            if self.use_v3:
                                logger.info("Fallback: Switching from v3 to v2 endpoint")
                                old_url = self.base_url
                                self.base_url = self.BASE_URL  # Switch to v2
                                self.use_v3 = False
                                try:
                                    response_data = self._make_request(params)
                                    logger.info("v2 endpoint successful - continuing with v2")
                                except SAMGovAPIError:
                                    # Restore original settings
                                    self.base_url = old_url
                                    self.use_v3 = True
                                    raise
                            else:
                                raise
                    else:
                        # Try v2 endpoint
                        if self.use_v3:
                            logger.info("Fallback: Switching from v3 to v2 endpoint")
                            old_url = self.base_url
                            self.base_url = self.BASE_URL  # Switch to v2
                            self.use_v3 = False
                            try:
                                response_data = self._make_request(params)
                                logger.info("v2 endpoint successful - continuing with v2")
                            except SAMGovAPIError:
                                # Restore original settings
                                self.base_url = old_url
                                self.use_v3 = True
                                raise
                        else:
                            raise
            else:
                raise
        
        # DEBUG: Log the complete raw response structure
        logger.info("=== RAW API RESPONSE DEBUG ===")
        logger.info(f"Response type: {type(response_data)}")
        logger.info(f"Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
        
        # Log all top-level fields and their types/lengths
        if isinstance(response_data, dict):
            for key, value in response_data.items():
                if isinstance(value, list):
                    logger.info(f"  {key}: list with {len(value)} items")
                    if len(value) > 0:
                        logger.info(f"    First item type: {type(value[0])}")
                        if isinstance(value[0], dict):
                            logger.info(f"    First item keys: {list(value[0].keys())}")
                elif isinstance(value, dict):
                    logger.info(f"  {key}: dict with {len(value)} keys: {list(value.keys())}")
                else:
                    logger.info(f"  {key}: {type(value).__name__} = {value}")
        
        # Process response - SAM.gov API returns data in 'opportunitiesData' field
        opportunities = response_data.get('opportunitiesData', [])
        
        # DEBUG: Log detailed response analysis
        logger.info("=== RESPONSE ANALYSIS ===")
        logger.info(f"Total records from API: {response_data.get('totalRecords', 'NOT FOUND')}")
        logger.info(f"Opportunities data field found: {'YES' if 'opportunitiesData' in response_data else 'NO'}")
        logger.info(f"Opportunities returned from API: {len(opportunities)}")
        
        # If no opportunities but totalRecords > 0, this indicates a potential issue
        total_records = response_data.get('totalRecords', 0)
        if total_records > 0 and len(opportunities) == 0:
            logger.warning(f"API indicates {total_records} total records available, but returned 0 opportunities!")
            logger.warning("This may indicate a pagination issue or API response format change.")
        
        # DEBUG: Log sample opportunity structure if available
        if opportunities:
            logger.info("=== SAMPLE OPPORTUNITY STRUCTURE ===")
            sample_opp = opportunities[0]
            logger.info(f"Sample opportunity keys: {list(sample_opp.keys())}")
            logger.info(f"Sample opportunity excerpts:")
            for key in ['title', 'solicitationNumber', 'noticeId', 'postedDate', 'naicsCode', 'fullParentPathName']:
                if key in sample_opp:
                    value = sample_opp[key]
                    display_value = str(value)[:100] + '...' if len(str(value)) > 100 else str(value)
                    logger.info(f"  {key}: {display_value}")
        else:
            logger.warning("No opportunities found in response to analyze structure")
        
        # Note: NAICS and agency filtering is now done server-side via API parameters
        # No client-side filtering needed since SAM.gov API handles this
        
        # Prepare response
        result = {
            'opportunities': opportunities,
            'total_count': len(opportunities),
            'limit': limit,
            'offset': offset,
            'api_total_records': response_data.get('totalRecords', 0),  # Add API's total count
            'filters': {
                'posted_from': posted_from.isoformat(),
                'posted_to': posted_to.isoformat(),
                'naics_codes': naics_codes,
                'agencies': agencies
            }
        }
        
        # DEBUG: Log final result summary
        logger.info("=== FINAL RESULT SUMMARY ===")
        logger.info(f"Opportunities after all filtering: {len(opportunities)}")
        logger.info(f"Result total_count: {result['total_count']}")
        logger.info(f"API reported total_records: {result['api_total_records']}")
        logger.info(f"Cache timeout: {cache_timeout} seconds")
        logger.info("=== END SAM.gov API Search Debug ===")
        
        # Enhance descriptions for opportunities if enabled and using v3 API
        if self.enable_description_enhancement and self.use_v3 and opportunities:
            logger.info("Enhancing descriptions for retrieved opportunities")
            for i, opp in enumerate(opportunities):
                try:
                    enhanced_description = self.get_enhanced_opportunity_description(opp)
                    if enhanced_description and enhanced_description != opp.get('description', ''):
                        opp['originalDescription'] = opp.get('description', '')
                        opp['description'] = enhanced_description
                        opp['descriptionEnhanced'] = True
                    else:
                        opp['descriptionEnhanced'] = False
                except Exception as e:
                    logger.warning(f"Failed to enhance description for opportunity {i}: {e}")
                    opp['descriptionEnhanced'] = False
        
        # Cache the result
        cache.set(cache_key, result, cache_timeout)
        
        return result
    
    def get_opportunity_details(self, notice_id: str, fetch_enhanced_description: bool = True) -> Dict[str, Any]:
        """
        Get detailed information about a specific opportunity.
        
        Args:
            notice_id: Opportunity notice ID
            fetch_enhanced_description: Whether to fetch enhanced description content
            
        Returns:
            Opportunity details with enhanced description if requested
        """
        cache_key = f"sam_gov_detail:{notice_id}:{fetch_enhanced_description}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Search for the specific notice using notice ID parameter
        # Use a 6-month date range to find the opportunity
        posted_from = datetime.now() - timedelta(days=180)  # 6 months back
        posted_to = datetime.now()  # Today
        
        params = {
            'limit': '100',  # Increase limit in case there are multiple matches
            'noticeid': notice_id,  # Use notice ID parameter
            'postedFrom': posted_from.strftime('%m/%d/%Y'),
            'postedTo': posted_to.strftime('%m/%d/%Y')
        }
        
        # Use the same fallback logic as search_opportunities
        try:
            response_data = self._make_request(params)
        except SAMGovAPIError as e:
            # If we get a 500 error after retries, try with v2 endpoint
            if "500" in str(e) or "INTERNAL SERVER ERROR" in str(e):
                logger.warning(f"Got 500 error for notice {notice_id}, trying v2 endpoint fallback...")
                
                # Try v2 endpoint if using v3
                if self.use_v3:
                    logger.info(f"Switching from v3 to v2 endpoint for notice {notice_id}")
                    old_url = self.base_url
                    self.base_url = self.BASE_URL  # Switch to v2
                    self.use_v3 = False
                    try:
                        response_data = self._make_request(params)
                        logger.info(f"v2 endpoint successful for notice {notice_id}")
                    except SAMGovAPIError:
                        # Restore original settings and re-raise
                        self.base_url = old_url
                        self.use_v3 = True
                        raise
                else:
                    raise
            else:
                raise
        opportunities = response_data.get('opportunitiesData', [])
        
        # Filter to find exact match
        matching_opportunity = None
        for opp in opportunities:
            if opp.get('noticeId') == notice_id:
                matching_opportunity = opp
                break
        
        if not matching_opportunity:
            raise SAMGovAPIError(f"Opportunity {notice_id} not found")
        
        # Enhance description if requested
        if fetch_enhanced_description:
            try:
                enhanced_description = self.get_enhanced_opportunity_description(matching_opportunity)
                if enhanced_description and enhanced_description != matching_opportunity.get('description', ''):
                    # Store both original and enhanced descriptions
                    matching_opportunity['originalDescription'] = matching_opportunity.get('description', '')
                    matching_opportunity['description'] = enhanced_description
                    matching_opportunity['descriptionEnhanced'] = True
                    logger.info(f"Enhanced description for opportunity {notice_id}")
            except Exception as e:
                logger.warning(f"Failed to enhance description for opportunity {notice_id}: {e}")
                matching_opportunity['descriptionEnhanced'] = False
        
        cache.set(cache_key, matching_opportunity, 3600)
        
        return matching_opportunity
    
    def get_opportunity_documents(self, opportunity: Dict[str, Any], extract_filenames: bool = True) -> List[Dict[str, str]]:
        """
        Extract document links from an opportunity with optional filename extraction.
        
        Args:
            opportunity: Opportunity data
            extract_filenames: Whether to extract actual filenames from URLs (default: True)
            
        Returns:
            List of document information with enhanced filename data
        """
        documents = []
        resource_urls = []
        
        # Extract from resourceLinks
        resource_links = opportunity.get('resourceLinks') or []
        if resource_links and isinstance(resource_links, list):
            for link in resource_links:
                # Use URL path as fallback name
                fallback_name = link.split('/')[-1] if '/' in link else 'Resource'
                documents.append({
                    'url': link,
                    'type': 'resource',
                    'name': fallback_name,  # Will be updated if filename extraction succeeds
                    'filename': None,
                    'filename_extracted': False
                })
                resource_urls.append(link)
        
        # Add additional info link if available
        if opportunity.get('additionalInfoLink'):
            documents.append({
                'url': opportunity['additionalInfoLink'],
                'type': 'additional_info',
                'name': 'Additional Information',
                'filename_extracted': False
            })
        
        # Add UI link for web access
        if opportunity.get('uiLink'):
            documents.append({
                'url': opportunity['uiLink'],
                'type': 'web_link',
                'name': 'View on SAM.gov',
                'filename_extracted': False
            })
        
        # Extract actual filenames for resource links if requested
        if extract_filenames and resource_urls:
            try:
                logger.info(f"Extracting filenames for {len(resource_urls)} resource URLs")
                filename_mapping = extract_filenames_from_urls(
                    resource_urls,
                    timeout=10.0,
                    max_retries=2,
                    retry_delay=1.0
                )
                
                # Update document names with extracted filenames
                for doc in documents:
                    if doc['type'] == 'resource' and doc['url'] in filename_mapping:
                        extracted_filename = filename_mapping[doc['url']]
                        if extracted_filename:
                            doc['name'] = extracted_filename
                            doc['filename_extracted'] = True
                            logger.debug(f"Updated filename for {doc['url']}: {extracted_filename}")
                        else:
                            logger.debug(f"Could not extract filename for {doc['url']}")
                
                logger.info(f"Successfully extracted {sum(1 for d in documents if d.get('filename_extracted'))} filenames")
                
            except Exception as e:
                logger.warning(f"Filename extraction failed for opportunity documents: {e}")
                # Continue with fallback names
        
        return documents
    
    def _get_description_cache_key(self, url: str) -> str:
        """
        Generate cache key for description content.
        
        Args:
            url: Description URL
            
        Returns:
            Cache key string
        """
        return f"sam_gov_description:{hash(url)}"
    
    def _build_sam_gov_url_with_api_key(self, url: str) -> str:
        """
        Build SAM.gov URL with API key parameter following specification.
        
        Implements the URL building logic from the FetchOpportunityDescription spec:
        - If URL already has query params, append '&api_key=...'
        - Otherwise append '?api_key=...'
        
        Args:
            url: Original SAM.gov URL
            
        Returns:
            URL with API key parameter
        """
        if not self.api_key:
            return url
            
        # Check if URL already has query parameters
        if '?' in url:
            # URL has existing query params, append with &
            return f"{url}&api_key={self.api_key}"
        else:
            # No existing query params, append with ?
            return f"{url}?api_key={self.api_key}"
    
    def _normalize_description_content(self, content: str, content_type: str) -> str:
        """
        Normalize description content based on content type following specification.
        
        Implements content normalization from the FetchOpportunityDescription spec:
        - If HTML: strip tags and preserve paragraphs & lists
        - If RTF/PDF: extract text if feasible with formatting note
        - Otherwise: return best-effort plaintext
        
        Args:
            content: Raw content from response
            content_type: HTTP content-type header value
            
        Returns:
            Normalized plain text content
        """
        if not content or not content.strip():
            return ""
        
        content = content.strip()
        
        # Handle HTML content
        if 'text/html' in content_type or content.lower().startswith(('<!doctype', '<html')):
            return self._extract_text_from_html(content)
        
        # Handle RTF content
        elif 'application/rtf' in content_type or content.startswith(r'{\rtf'):
            # Basic RTF text extraction
            try:
                # Remove RTF control codes and extract readable text
                import re
                # Remove RTF control words and groups
                text = re.sub(r'\\[a-z]+\d*\s?', '', content)
                text = re.sub(r'[{}]', '', text)
                text = re.sub(r'\s+', ' ', text)
                
                if text.strip():
                    return f"{text.strip()}\n\n[Note: Content was in RTF format and may have formatting differences]"
                else:
                    return "[RTF content could not be processed - please view original document]"
            except Exception:
                return "[RTF content could not be processed - please view original document]"
        
        # Handle PDF content (basic)
        elif 'application/pdf' in content_type or content.startswith('%PDF'):
            return "[PDF content detected - please view original document for full content]"
        
        # Handle JSON content
        elif 'application/json' in content_type:
            try:
                import json
                data = json.loads(content)
                # Try to extract meaningful text from JSON
                if isinstance(data, dict):
                    text_fields = []
                    for key, value in data.items():
                        if isinstance(value, str) and len(value) > 20:
                            text_fields.append(f"{key.title()}: {value}")
                    if text_fields:
                        return '\n\n'.join(text_fields)
                return "[JSON content - no extractable text found]"
            except Exception:
                return content  # Return as-is if JSON parsing fails
        
        # Plain text or unknown format - return as-is with basic cleanup
        else:
            # Basic text cleanup
            import re
            # Remove excessive whitespace
            text = re.sub(r'\s+', ' ', content)
            # Remove control characters but preserve newlines
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
            return text.strip()
    
    def _fetch_description_content(self, url: str, timeout: int = None) -> Optional[str]:
        """
        Fetch description content from a URL with enhanced SAM.gov support.
        
        This method implements the SAM.gov noticedesc endpoint specification:
        - Properly handles SAM.gov description links with API key authentication
        - Implements retry logic with exponential backoff for 5xx errors
        - Normalizes HTML/RTF content to plain text
        - Handles "Description Not Found" responses
        
        Args:
            url: URL to fetch description content from
            timeout: Request timeout in seconds
            
        Returns:
            Description content or None if failed/not found
        """
        if not url or not self.enable_description_enhancement:
            return None
            
        # Use configured timeout with sensible defaults for SAM.gov
        if timeout is None:
            timeout = self.description_fetch_timeout
        
        # For SAM.gov URLs, use stricter timeouts as per spec
        parsed_url = urlparse(url)
        is_sam_gov_url = 'sam.gov' in parsed_url.netloc.lower()
        if is_sam_gov_url:
            connect_timeout = 5  # 5s connect timeout per spec
            read_timeout = 20    # 20s read timeout per spec
        else:
            connect_timeout = timeout
            read_timeout = timeout
            
        # Check cache first
        cache_key = self._get_description_cache_key(url)
        cached_content = cache.get(cache_key)
        if cached_content is not None:
            logger.debug(f"Using cached description content for {url}")
            return cached_content
        
        try:
            logger.info(f"Fetching description content from: {url}")
            
            # Build URL with API key for SAM.gov URLs
            final_url = self._build_sam_gov_url_with_api_key(url) if is_sam_gov_url else url
            
            headers = {
                'User-Agent': 'BLACK CORAL Government Contracting System',
                'Accept': 'text/html,application/json,text/plain,application/*'
            }
            
            # Implement retry logic with exponential backoff for SAM.gov URLs
            max_retries = 3 if is_sam_gov_url else 1
            base_delay = 0.5  # 500ms base delay per spec
            backoff_factor = 2.0
            
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        # Exponential backoff with jitter
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        jitter = random.uniform(0, delay * 0.1)
                        sleep_time = delay + jitter
                        logger.info(f"Retrying description fetch (attempt {attempt + 1}/{max_retries + 1}) after {sleep_time:.2f}s")
                        time.sleep(sleep_time)
                    
                    response = requests.get(
                        final_url,
                        headers=headers,
                        timeout=(connect_timeout, read_timeout),
                        allow_redirects=True
                    )
                    
                    if response.status_code == 200:
                        content = response.text.strip()
                        
                        # Check for "Description Not Found" responses
                        if 'description not found' in content.lower():
                            logger.info(f"Description not found for URL: {url}")
                            cache.set(cache_key, '', self.description_cache_ttl)
                            return None
                        
                        # Normalize content based on content type
                        content_type = response.headers.get('content-type', '').lower()
                        normalized_content = self._normalize_description_content(content, content_type)
                        
                        if normalized_content and len(normalized_content.strip()) > 10:
                            # Cache successful results
                            cache.set(cache_key, normalized_content, self.description_cache_ttl)
                            logger.debug(f"Successfully fetched {len(normalized_content)} characters from {url}")
                            return normalized_content
                        else:
                            logger.warning(f"Description content too short or empty from {url}")
                            cache.set(cache_key, '', 600)
                            return None
                    
                    elif response.status_code in [500, 502, 503, 504] and is_sam_gov_url and attempt < max_retries:
                        # Retry on 5xx errors for SAM.gov URLs
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"Got {response.status_code} from {url}, will retry...")
                        continue
                    else:
                        logger.warning(f"Failed to fetch description from {url}: HTTP {response.status_code}")
                        # Cache failed result for shorter time
                        cache.set(cache_key, '', 600)
                        return None
                        
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    if attempt < max_retries and is_sam_gov_url:
                        logger.warning(f"Request failed for {url}: {e}, will retry...")
                        continue
                    else:
                        break
            
            # All retries exhausted
            logger.warning(f"All retries exhausted for {url}. Last error: {last_error}")
            cache.set(cache_key, '', 600)
            return None
                
        except Exception as e:
            logger.error(f"Unexpected error fetching description from {url}: {e}")
            return None
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """
        Extract meaningful text content from HTML.
        
        Args:
            html_content: HTML content string
            
        Returns:
            Extracted text content
        """
        try:
            # Try to use BeautifulSoup if available
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.extract()
                
                # Get text content
                text = soup.get_text()
                
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                return text[:5000]  # Limit to 5000 characters
                
            except ImportError:
                # Fallback: simple text extraction without BeautifulSoup
                import re
                # Remove script and style tags
                text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                # Remove all HTML tags
                text = re.sub(r'<[^>]+>', '', text)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:5000]  # Limit to 5000 characters
                
        except Exception as e:
            logger.warning(f"Failed to extract text from HTML: {e}")
            return html_content[:1000]  # Return first 1000 chars as fallback
    
    def fetch_opportunity_description_by_notice_id(self, notice_id: str) -> Dict[str, Any]:
        """
        Fetch opportunity description using the SAM.gov noticedesc endpoint.
        
        This method implements the exact specification from the FetchOpportunityDescription prompt:
        - Uses the noticedesc endpoint with notice ID
        - Implements proper retry policy for 5xx errors
        - Handles "Description Not Found" responses
        - Returns structured response with status and error handling
        
        Args:
            notice_id: The SAM.gov notice ID
            
        Returns:
            Dict with status and either description_text or error information
        """
        if not notice_id:
            return {
                "status": "error",
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Notice ID is required",
                    "http_status": None,
                    "body_sample": None
                }
            }
        
        # Build the noticedesc URL as per specification
        base_url = "https://api.sam.gov/prod/opportunities/v1/noticedesc"
        description_link = f"{base_url}?noticeid={notice_id}"
        
        logger.info(f"Fetching description for notice ID: {notice_id}")
        
        try:
            # Build final URL with API key
            final_url = self._build_sam_gov_url_with_api_key(description_link)
            
            headers = {
                'User-Agent': 'BLACK CORAL Government Contracting System',
                'Accept': 'text/html,application/json,text/plain,application/*'
            }
            
            # Implement retry policy as per specification
            max_retries = 3
            base_delay_ms = 500
            backoff_factor = 2.0
            
            last_error = None
            last_response = None
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        # Exponential backoff with jitter
                        delay_ms = base_delay_ms * (backoff_factor ** (attempt - 1))
                        jitter_ms = random.uniform(0, delay_ms * 0.1)
                        sleep_time = (delay_ms + jitter_ms) / 1000.0
                        logger.info(f"Retrying description fetch (attempt {attempt + 1}/{max_retries + 1}) after {sleep_time:.2f}s")
                        time.sleep(sleep_time)
                    
                    response = requests.get(
                        final_url,
                        headers=headers,
                        timeout=(5, 20),  # 5s connect, 20s read as per spec
                        allow_redirects=True
                    )
                    
                    last_response = response
                    
                    if response.status_code == 200:
                        content = response.text.strip()
                        body_sample = content[:200] if content else ""
                        
                        # Check for "Description Not Found" as per specification
                        if 'description not found' in content.lower():
                            return {
                                "status": "error",
                                "error": {
                                    "code": "NOT_FOUND",
                                    "message": "Description not found for this notice ID. The opportunity may not have a detailed description or the notice ID may be invalid.",
                                    "http_status": 200,
                                    "body_sample": body_sample
                                }
                            }
                        
                        # Normalize content
                        content_type = response.headers.get('content-type', '').lower()
                        normalized_content = self._normalize_description_content(content, content_type)
                        
                        if normalized_content and len(normalized_content.strip()) > 10:
                            return {
                                "status": "ok",
                                "noticeId": notice_id,
                                "description_text": normalized_content
                            }
                        else:
                            return {
                                "status": "error",
                                "error": {
                                    "code": "NOT_FOUND",
                                    "message": "Description content is empty or too short",
                                    "http_status": 200,
                                    "body_sample": body_sample
                                }
                            }
                    
                    elif response.status_code in [500, 502, 503, 504] and attempt < max_retries:
                        # Retry on 5xx errors as per specification
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"Got {response.status_code} from noticedesc endpoint, will retry...")
                        continue
                    
                    elif response.status_code == 401:
                        return {
                            "status": "error",
                            "error": {
                                "code": "INVALID_KEY",
                                "message": "API key is invalid or missing. Please check your SAM.gov API key configuration.",
                                "http_status": 401,
                                "body_sample": response.text[:200] if response.text else ""
                            }
                        }
                    
                    elif response.status_code == 404:
                        return {
                            "status": "error",
                            "error": {
                                "code": "NOT_FOUND",
                                "message": "Notice ID not found. The opportunity may not exist or may be outside the searchable date range.",
                                "http_status": 404,
                                "body_sample": response.text[:200] if response.text else ""
                            }
                        }
                    
                    else:
                        return {
                            "status": "error",
                            "error": {
                                "code": "UPSTREAM_5XX" if 500 <= response.status_code < 600 else "HTTP_ERROR",
                                "message": f"SAM.gov API returned HTTP {response.status_code}. Please try again later.",
                                "http_status": response.status_code,
                                "body_sample": response.text[:200] if response.text else ""
                            }
                        }
                        
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        logger.warning(f"Request failed for notice {notice_id}: {e}, will retry...")
                        continue
                    else:
                        break
            
            # All retries exhausted
            return {
                "status": "error",
                "error": {
                    "code": "NETWORK",
                    "message": f"Failed to fetch description after {max_retries + 1} attempts. Last error: {last_error}",
                    "http_status": last_response.status_code if last_response else None,
                    "body_sample": last_response.text[:200] if last_response and last_response.text else ""
                }
            }
            
        except Exception as e:
            logger.error(f"Unexpected error fetching description for notice {notice_id}: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "NETWORK",
                    "message": f"Unexpected error: {str(e)}",
                    "http_status": None,
                    "body_sample": None
                }
            }
    
    def get_enhanced_opportunity_description(self, opportunity_data: Dict[str, Any]) -> str:
        """
        Get enhanced description content for an opportunity.
        
        This method checks for description content in the following order:
        1. Direct description field in the opportunity data
        2. Description URL in resourceLinks
        3. Additional info link content
        4. Full description field if available in v3 API
        
        Args:
            opportunity_data: Opportunity data from SAM.gov API
            
        Returns:
            Enhanced description content
        """
        # Start with existing description
        description = opportunity_data.get('description', '').strip()
        
        # Check for description URLs in various fields
        description_urls = []
        
        # Check resourceLinks for description content
        resource_links = opportunity_data.get('resourceLinks', [])
        for link in resource_links:
            if isinstance(link, str):
                # Simple URL string
                if any(keyword in link.lower() for keyword in ['description', 'synopsis', 'details', 'solicitation']):
                    description_urls.append(link)
            elif isinstance(link, dict):
                # Structured resource link
                url = link.get('url') or link.get('link')
                link_type = link.get('type', '').lower()
                if url and ('description' in link_type or 'synopsis' in link_type or 'solicitation' in link_type):
                    description_urls.append(url)
        
        # Check for specific description-related fields
        for field_name in ['descriptionLink', 'synopsisLink', 'fullDescriptionLink', 'solicitationLink']:
            url = opportunity_data.get(field_name)
            if url:
                description_urls.append(url)
        
        # Check additionalInfoLink as fallback
        additional_info = opportunity_data.get('additionalInfoLink')
        if additional_info and not description_urls:
            description_urls.append(additional_info)
        
        # Fetch content from description URLs if enhancement is enabled
        fetched_descriptions = []
        if self.enable_description_enhancement:
            for url in description_urls[:3]:  # Limit to first 3 URLs to avoid excessive requests
                content = self._fetch_description_content(url)
                if content and len(content.strip()) > self.min_enhancement_length:  # Only use substantial content
                    fetched_descriptions.append(content)
        
        # Combine descriptions intelligently
        if fetched_descriptions:
            # If original description is short or generic, prioritize fetched content
            if len(description) < 100 or any(generic in description.lower() for generic in ['see attachment', 'see solicitation', 'refer to']):
                # Use fetched content as primary description
                enhanced_description = ' '.join(fetched_descriptions)
                if description and description not in enhanced_description:
                    enhanced_description = f"{description}\n\n{enhanced_description}"
            else:
                # Append fetched content to existing description
                enhanced_description = f"{description}\n\n{' '.join(fetched_descriptions)}"
            
            # Limit total length using configured max
            enhanced_description = enhanced_description[:self.max_description_length]
            
            logger.info(f"Enhanced description from {len(description)} to {len(enhanced_description)} characters")
            return enhanced_description
        
        return description
    
    def _normalize_opportunity_data(self, opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize opportunity data for AI analysis services."""
        return {
            'title': opportunity_data.get('title', ''),
            'solicitation_number': opportunity_data.get('solicitationNumber', ''),
            'notice_id': opportunity_data.get('noticeId', ''),
            'agency_name': opportunity_data.get('fullParentPathName', ''),
            'posted_date': opportunity_data.get('postedDate', ''),
            'response_date': opportunity_data.get('responseDeadLine', ''),
            'description': opportunity_data.get('description', ''),
            'opportunity_type': opportunity_data.get('type', ''),
            'set_aside_type': opportunity_data.get('typeOfSetAsideDescription', ''),
            'naics_codes': [opportunity_data.get('naicsCode', '')] if opportunity_data.get('naicsCode') else [],
            'place_of_performance': opportunity_data.get('placeOfPerformance', {}),
            'point_of_contact': opportunity_data.get('pointOfContact', {})
        }
    
    def _run_ai_analysis(self, prompt: str, system_prompt: str, analysis_type: str) -> Dict[str, Any]:
        """Run AI analysis with error handling."""
        from apps.ai_integration.ai_providers import ai_manager, AIRequest, ModelType
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model_type=ModelType.ANALYSIS,
            max_tokens=3000,
            temperature=0.3
        )
        
        response = ai_manager.generate_response(request, preferred_provider=AIProvider.CLAUDE)
        
        return {
            'analysis': response.content,
            'model_used': response.model,
            'provider': response.provider.value,
            'confidence_score': 0.8,  # Default confidence
            'generated_at': timezone.now().isoformat(),
            'tokens_used': response.tokens_used,
            'processing_time': response.processing_time
        }
    
    def _build_risk_assessment_prompt(self, opportunity_data: Dict[str, Any]) -> str:
        """Build detailed risk assessment prompt."""
        return f"""
GOVERNMENT CONTRACTING RISK ASSESSMENT

Opportunity: {opportunity_data.get('title', 'N/A')}
Agency: {opportunity_data.get('fullParentPathName', 'N/A')}
Solicitation: {opportunity_data.get('solicitationNumber', 'N/A')}
Response Due: {opportunity_data.get('responseDeadLine', 'N/A')}
Set-Aside: {opportunity_data.get('typeOfSetAsideDescription', 'N/A')}

Description:
{opportunity_data.get('description', 'No description available')}

Please provide a comprehensive risk assessment covering all major risk categories.
"""
    
    def _build_competitive_analysis_prompt(self, opportunity_data: Dict[str, Any]) -> str:
        """Build competitive analysis prompt."""
        return f"""
GOVERNMENT CONTRACTING COMPETITIVE ANALYSIS

Opportunity: {opportunity_data.get('title', 'N/A')}
Agency: {opportunity_data.get('fullParentPathName', 'N/A')}
NAICS Code: {opportunity_data.get('naicsCode', 'N/A')}
Set-Aside Type: {opportunity_data.get('typeOfSetAsideDescription', 'N/A')}

Description:
{opportunity_data.get('description', 'No description available')}

Analyze the competitive landscape and market opportunity.
"""
    
    def _generate_bid_recommendation(self, opportunity_data: Dict[str, Any], 
                                   analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive bid recommendation based on all analyses."""
        
        # Extract key insights from analyses
        opportunity_analysis = analysis_results.get('opportunity_analysis', {})
        compliance_check = analysis_results.get('compliance_check', {})
        risk_assessment = analysis_results.get('risk_assessment', {})
        competitive_analysis = analysis_results.get('competitive_analysis', {})
        
        # Calculate recommendation score
        score_factors = {
            'opportunity_confidence': opportunity_analysis.get('confidence_score', 0.5),
            'compliance_status': 1.0 if compliance_check.get('overall_status') == 'COMPLIANT' else 0.3,
            'risk_level': 0.8,  # Default - would parse from risk assessment
            'competitive_strength': 0.6  # Default - would parse from competitive analysis
        }
        
        overall_score = sum(score_factors.values()) / len(score_factors)
        
        # Determine recommendation
        if overall_score >= 0.75:
            recommendation = "PURSUE"
            confidence = "HIGH"
        elif overall_score >= 0.6:
            recommendation = "QUALIFIED_PURSUE"
            confidence = "MEDIUM"
        elif overall_score >= 0.4:
            recommendation = "WATCH"
            confidence = "MEDIUM"
        else:
            recommendation = "PASS"
            confidence = "HIGH"
        
        # Generate recommendation prompt
        rec_prompt = f"""
BID/NO-BID DECISION ANALYSIS

Opportunity: {opportunity_data.get('title', 'N/A')}
Overall Analysis Score: {overall_score:.2f}

Key Findings:
- Opportunity Confidence: {score_factors['opportunity_confidence']:.2f}
- Compliance Status: {compliance_check.get('overall_status', 'Unknown')}
- Risk Assessment Available: {bool(risk_assessment)}
- Competitive Analysis Available: {bool(competitive_analysis)}

Generate a strategic bid recommendation with:
1. Clear GO/NO-GO/WATCH recommendation
2. Key supporting rationale
3. Critical success factors
4. Resource requirements estimate
5. Timeline considerations
6. Next steps if pursuing
"""
        
        try:
            ai_recommendation = self._run_ai_analysis(
                prompt=rec_prompt,
                system_prompt="""You are a senior government contracting strategist making bid/no-bid decisions. 
                Provide a clear, actionable recommendation based on the analysis data. Be direct and strategic.""",
                analysis_type="bid_recommendation"
            )
            
            return {
                'recommendation': recommendation,
                'confidence_level': confidence,
                'overall_score': overall_score,
                'score_factors': score_factors,
                'ai_analysis': ai_recommendation,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"AI bid recommendation failed: {e}")
            return {
                'recommendation': recommendation,
                'confidence_level': confidence,
                'overall_score': overall_score,
                'score_factors': score_factors,
                'ai_analysis': {'analysis': 'AI analysis unavailable'},
                'error': str(e),
                'generated_at': timezone.now().isoformat()
            }
    
    def _generate_analysis_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of all analyses."""
        summary = {
            'total_analyses': len(results),
            'successful_analyses': [key for key in results.keys()],
            'key_insights': [],
            'overall_recommendation': None,
            'confidence_scores': {}
        }
        
        # Extract confidence scores
        for analysis_type, data in results.items():
            if isinstance(data, dict) and 'confidence_score' in data:
                summary['confidence_scores'][analysis_type] = data['confidence_score']
        
        # Get overall recommendation if available
        if 'bid_recommendation' in results:
            summary['overall_recommendation'] = results['bid_recommendation'].get('recommendation')
        
        # Extract key insights
        if 'opportunity_analysis' in results:
            oa = results['opportunity_analysis']
            if oa.get('executive_summary'):
                summary['key_insights'].append(f"Opportunity: {oa['executive_summary'][:100]}...")
        
        if 'compliance_check' in results:
            cc = results['compliance_check']
            summary['key_insights'].append(f"Compliance: {cc.get('overall_status', 'Unknown')}")
        
        return summary