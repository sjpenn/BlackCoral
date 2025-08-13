#!/usr/bin/env python
"""
Live server test script for BLACK CORAL application.
Tests the actual running server at localhost:8000.
"""

import requests
import sys

def test_endpoint(url, expected_status, description):
    """Test an endpoint and return success status."""
    try:
        response = requests.get(url, allow_redirects=False, timeout=5)
        if response.status_code == expected_status:
            print(f"✅ {description}: {response.status_code}")
            return True
        else:
            print(f"❌ {description}: Expected {expected_status}, got {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ {description}: Connection error - {e}")
        return False

def test_auth_flow():
    """Test the authentication flow."""
    session = requests.Session()
    
    # Get login page and extract CSRF token
    try:
        login_page = session.get('http://localhost:8000/auth/login/', timeout=5)
        if login_page.status_code != 200:
            print(f"❌ Login page access failed: {login_page.status_code}")
            return False
            
        # Extract CSRF token from response
        import re
        csrf_match = re.search(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*value="([^"]*)"', login_page.text)
        if not csrf_match:
            print("❌ CSRF token not found in login form")
            return False
            
        csrf_token = csrf_match.group(1)
        
        # Attempt login
        login_data = {
            'username': 'admin',
            'password': 'admin123',
            'csrfmiddlewaretoken': csrf_token
        }
        
        login_response = session.post(
            'http://localhost:8000/auth/login/', 
            data=login_data,
            allow_redirects=False,
            timeout=5
        )
        
        if login_response.status_code == 302 and '/dashboard/' in login_response.headers.get('Location', ''):
            print("✅ Authentication flow: Login successful, redirects to dashboard")
            
            # Test accessing dashboard as authenticated user
            dashboard_response = session.get('http://localhost:8000/dashboard/', timeout=5)
            if dashboard_response.status_code == 200:
                print("✅ Dashboard access: Authenticated user can access dashboard")
                return True
            else:
                print(f"❌ Dashboard access failed: {dashboard_response.status_code}")
                return False
        else:
            print(f"❌ Authentication failed: {login_response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Authentication flow error: {e}")
        return False

def main():
    """Run all tests."""
    print("BLACK CORAL Live Server Test")
    print("=" * 40)
    print("Testing server at http://localhost:8000")
    print()
    
    # Test basic endpoints
    tests = [
        ('http://localhost:8000/', 200, 'Landing page loads'),
        ('http://localhost:8000/dashboard/', 302, 'Dashboard redirects to login'),
        ('http://localhost:8000/auth/login/', 200, 'Login page loads'),
        ('http://localhost:8000/health/', 200, 'Health check endpoint'),
        ('http://localhost:8000/admin/', 302, 'Admin interface available'),
    ]
    
    passed = 0
    total = len(tests) + 1  # +1 for auth flow test
    
    for url, expected_status, description in tests:
        if test_endpoint(url, expected_status, description):
            passed += 1
    
    print()
    
    # Test authentication flow
    if test_auth_flow():
        passed += 1
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! BLACK CORAL is working correctly.")
        print()
        print("Ready to use:")
        print("- Landing page: http://localhost:8000/")
        print("- Login: admin/admin123")
        print("- Dashboard: http://localhost:8000/dashboard/")
        return 0
    else:
        print("❌ Some tests failed. Check server configuration.")
        return 1

if __name__ == '__main__':
    sys.exit(main())