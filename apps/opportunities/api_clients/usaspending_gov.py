"""
USASpending.gov API Client for historical spending data analysis

This module provides access to USASpending.gov data to complement SAM.gov opportunities
with historical spending patterns, agency funding trends, and NAICS-based analysis.
"""

import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
import time

logger = logging.getLogger(__name__)


class USASpendingClient:
    """Client for USASpending.gov API with caching and error handling"""
    
    BASE_URL = "https://api.usaspending.gov/api/v2"
    
    # No authentication required for USASpending.gov
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests to be respectful
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'BlackCoral-GovContracting/1.0'
        })
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - time_since_last)
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make API request with error handling and caching"""
        
        # Try to get cached result, but don't fail if cache is unavailable
        cache_key = f"usaspending_{endpoint}_{hash(str(data))}"
        cached_result = None
        try:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"Using cached USASpending data for {endpoint}")
                return cached_result
        except Exception as e:
            logger.warning(f"Cache unavailable for USASpending request: {e}")
            # Continue without cache
        
        self._rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            if data:
                response = self.session.post(url, json=data, timeout=30)
            else:
                response = self.session.get(url, timeout=30)
            
            response.raise_for_status()
            result = response.json()
            
            # Try to cache for 1 hour, but don't fail if cache is unavailable
            try:
                cache.set(cache_key, result, 3600)
            except Exception as e:
                logger.warning(f"Could not cache USASpending response: {e}")
            
            logger.info(f"USASpending API request successful: {endpoint}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"USASpending API request failed for {endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in USASpending request: {e}")
            return None
    
    def get_spending_by_naics(self, naics_codes: List[str], 
                             fiscal_years: List[int] = None) -> Dict[str, Any]:
        """Get historical spending data by NAICS codes"""
        
        if fiscal_years is None:
            # Default to last 3 fiscal years
            current_year = datetime.now().year
            fiscal_years = [current_year - 2, current_year - 1, current_year]
        
        filters = {
            "naics_codes": naics_codes,
            "time_period": [
                {
                    "start_date": f"{year}-10-01",
                    "end_date": f"{year + 1}-09-30"
                } for year in fiscal_years
            ]
        }
        
        data = {
            "filters": filters,
            "category": "naics",
            "subawards": False
        }
        
        return self._make_request("/search/spending_by_category/", data)
    
    def get_spending_by_agency(self, agency_ids: List[str],
                              fiscal_years: List[int] = None) -> Dict[str, Any]:
        """Get historical spending data by agencies"""
        
        if fiscal_years is None:
            current_year = datetime.now().year
            fiscal_years = [current_year - 2, current_year - 1, current_year]
        
        filters = {
            "agencies": [{"type": "awarding", "tier": "toptier", "name": agency_id} 
                        for agency_id in agency_ids],
            "time_period": [
                {
                    "start_date": f"{year}-10-01", 
                    "end_date": f"{year + 1}-09-30"
                } for year in fiscal_years
            ]
        }
        
        data = {
            "filters": filters,
            "category": "awarding_agency",
            "subawards": False
        }
        
        return self._make_request("/search/spending_by_category/", data)
    
    def get_spending_trends(self, naics_codes: List[str] = None,
                           agency_ids: List[str] = None,
                           months_back: int = 24) -> Dict[str, Any]:
        """Get spending trends over time"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)
        
        filters = {
            "time_period": [{
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }]
        }
        
        if naics_codes:
            filters["naics_codes"] = naics_codes
        
        if agency_ids:
            filters["agencies"] = [
                {"type": "awarding", "tier": "toptier", "name": agency_id}
                for agency_id in agency_ids
            ]
        
        data = {
            "group": "quarter",
            "filters": filters
        }
        
        return self._make_request("/search/spending_over_time/", data)
    
    def get_top_contractors_by_naics(self, naics_codes: List[str],
                                   fiscal_years: List[int] = None,
                                   limit: int = 10) -> Dict[str, Any]:
        """Get top contractors in specific NAICS codes"""
        
        if fiscal_years is None:
            current_year = datetime.now().year
            fiscal_years = [current_year - 1, current_year]
        
        filters = {
            "naics_codes": naics_codes,
            "time_period": [
                {
                    "start_date": f"{year}-10-01",
                    "end_date": f"{year + 1}-09-30"
                } for year in fiscal_years
            ]
        }
        
        data = {
            "filters": filters,
            "category": "recipient",
            "limit": limit,
            "subawards": False
        }
        
        return self._make_request("/search/spending_by_category/", data)
    
    def search_awards_by_opportunity(self, solicitation_number: str = None,
                                   agency_name: str = None,
                                   award_amount_min: float = None) -> Dict[str, Any]:
        """Search for related awards that might match an opportunity"""
        
        filters = {}
        
        if solicitation_number:
            filters["keyword"] = solicitation_number
        
        if agency_name:
            filters["agencies"] = [{
                "type": "awarding",
                "tier": "toptier", 
                "name": agency_name
            }]
        
        if award_amount_min:
            filters["award_amounts"] = [{
                "lower_bound": award_amount_min
            }]
        
        # Search recent awards (last 2 years)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)
        filters["time_period"] = [{
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }]
        
        data = {
            "filters": filters,
            "fields": [
                "Award ID", "Recipient Name", "Award Amount",
                "Award Date", "Description", "Awarding Agency",
                "NAICS Code", "NAICS Description"
            ],
            "page": 1,
            "limit": 50,
            "sort": "Award Amount",
            "order": "desc"
        }
        
        return self._make_request("/search/spending_by_award/", data)
    
    def get_agency_spending_summary(self, agency_name: str,
                                  fiscal_year: int = None) -> Dict[str, Any]:
        """Get comprehensive spending summary for an agency"""
        
        if fiscal_year is None:
            fiscal_year = datetime.now().year
        
        filters = {
            "agencies": [{
                "type": "awarding",
                "tier": "toptier",
                "name": agency_name
            }],
            "time_period": [{
                "start_date": f"{fiscal_year}-10-01",
                "end_date": f"{fiscal_year + 1}-09-30"
            }]
        }
        
        # Get multiple views of agency spending
        results = {}
        
        # By NAICS
        naics_data = {
            "filters": filters,
            "category": "naics",
            "limit": 20
        }
        results['by_naics'] = self._make_request("/search/spending_by_category/", naics_data)
        
        # By recipient
        recipient_data = {
            "filters": filters,
            "category": "recipient", 
            "limit": 20
        }
        results['by_recipient'] = self._make_request("/search/spending_by_category/", recipient_data)
        
        return results
    
    def analyze_opportunity_context(self, opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze USASpending context for a specific opportunity"""
        
        analysis = {
            'naics_spending': None,
            'agency_spending': None,
            'similar_awards': None,
            'spending_trends': None,
            'top_contractors': None
        }
        
        try:
            # Extract relevant data from opportunity
            naics_codes = opportunity_data.get('naics_codes', [])
            agency_name = opportunity_data.get('agency_name')
            
            if naics_codes:
                # Get spending by NAICS
                analysis['naics_spending'] = self.get_spending_by_naics(naics_codes)
                
                # Get spending trends
                analysis['spending_trends'] = self.get_spending_trends(naics_codes=naics_codes)
                
                # Get top contractors
                analysis['top_contractors'] = self.get_top_contractors_by_naics(naics_codes)
            
            if agency_name:
                # Get agency spending summary  
                analysis['agency_spending'] = self.get_agency_spending_summary(agency_name)
            
            # Search for similar awards
            solicitation_number = opportunity_data.get('solicitation_number')
            if solicitation_number or agency_name:
                analysis['similar_awards'] = self.search_awards_by_opportunity(
                    solicitation_number=solicitation_number,
                    agency_name=agency_name
                )
                
        except Exception as e:
            logger.error(f"Error analyzing opportunity context: {e}")
        
        return analysis


# Convenience function for quick access
def get_usaspending_client() -> USASpendingClient:
    """Get configured USASpending client"""
    return USASpendingClient()