"""
SAM.gov Opportunities API Client for BLACK CORAL
Implements opportunity discovery from sam.gov with rate limiting and caching.
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

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
    """
    
    BASE_URL = "https://api.sam.gov/prod/opportunities/v2/search"
    ALPHA_URL = "https://api-alpha.sam.gov/prodlike/opportunities/v2/search"
    
    # Rate limits by account type
    RATE_LIMITS = {
        'non_federal': 10,
        'entity_associated': 1000,
        'federal_system': 10000
    }
    
    def __init__(self, api_key: str = None, use_alpha: bool = False):
        """
        Initialize SAM.gov API client.
        
        Args:
            api_key: SAM.gov public API key
            use_alpha: Use alpha/testing endpoint if True
        """
        self.api_key = api_key or settings.SAM_GOV_API_KEY
        self.base_url = self.ALPHA_URL if use_alpha else self.BASE_URL
        self.account_type = getattr(settings, 'SAM_GOV_ACCOUNT_TYPE', 'non_federal')
        self.daily_limit = self.RATE_LIMITS.get(self.account_type, 10)
        
        if not self.api_key:
            raise SAMGovAPIError("SAM.gov API key is required")
    
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
    
    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with error handling.
        
        Args:
            params: Query parameters
            
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
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=30,
                headers={
                    'User-Agent': 'BLACK CORAL Government Contracting System',
                    'Accept': 'application/json'
                }
            )
            
            # Increment rate limit counter
            self._increment_rate_limit()
            
            # Check for errors
            if response.status_code == 429:
                raise SAMGovAPIError("Rate limit exceeded")
            elif response.status_code == 401:
                raise SAMGovAPIError("Invalid API key")
            elif response.status_code != 200:
                raise SAMGovAPIError(f"API error: {response.status_code} - {response.text}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SAM.gov API request failed: {e}")
            raise SAMGovAPIError(f"Request failed: {str(e)}")
    
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
        
        # Check cache first
        cache_key = self._get_cache_key(params)
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Returning cached data for {cache_key}")
            return cached_data
        
        # Make API request
        response_data = self._make_request(params)
        
        # Process response
        opportunities = response_data.get('opportunities', [])
        
        # Apply client-side NAICS filtering if needed
        if naics_codes:
            opportunities = [
                opp for opp in opportunities
                if opp.get('naicsCode') in naics_codes
            ]
        
        # Apply client-side agency filtering if needed
        if agencies:
            opportunities = [
                opp for opp in opportunities
                if any(agency.lower() in opp.get('fullParentPathName', '').lower() 
                      for agency in agencies)
            ]
        
        # Prepare response
        result = {
            'opportunities': opportunities,
            'total_count': len(opportunities),
            'limit': limit,
            'offset': offset,
            'filters': {
                'posted_from': posted_from.isoformat(),
                'posted_to': posted_to.isoformat(),
                'naics_codes': naics_codes,
                'agencies': agencies
            }
        }
        
        # Cache the result
        cache.set(cache_key, result, cache_timeout)
        
        return result
    
    def get_opportunity_details(self, notice_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific opportunity.
        
        Args:
            notice_id: Opportunity notice ID
            
        Returns:
            Opportunity details
        """
        # For now, we need to search and filter
        # The API may not have a direct detail endpoint
        cache_key = f"sam_gov_detail:{notice_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Search for the specific notice
        params = {
            'limit': '1',
            'solnum': notice_id,
            'postedFrom': (datetime.now() - timedelta(days=365)).strftime('%m/%d/%Y'),
            'postedTo': datetime.now().strftime('%m/%d/%Y')
        }
        
        response_data = self._make_request(params)
        opportunities = response_data.get('opportunities', [])
        
        if not opportunities:
            raise SAMGovAPIError(f"Opportunity {notice_id} not found")
        
        opportunity = opportunities[0]
        cache.set(cache_key, opportunity, 3600)
        
        return opportunity
    
    def get_opportunity_documents(self, opportunity: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract document links from an opportunity.
        
        Args:
            opportunity: Opportunity data
            
        Returns:
            List of document information
        """
        documents = []
        
        # Extract from resourceLinks
        resource_links = opportunity.get('resourceLinks', [])
        for link in resource_links:
            documents.append({
                'url': link,
                'type': 'resource',
                'name': link.split('/')[-1] if '/' in link else 'Resource'
            })
        
        # Add additional info link if available
        if opportunity.get('additionalInfoLink'):
            documents.append({
                'url': opportunity['additionalInfoLink'],
                'type': 'additional_info',
                'name': 'Additional Information'
            })
        
        # Add UI link for web access
        if opportunity.get('uiLink'):
            documents.append({
                'url': opportunity['uiLink'],
                'type': 'web_link',
                'name': 'View on SAM.gov'
            })
        
        return documents