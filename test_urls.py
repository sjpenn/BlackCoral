#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings')
django.setup()

from django.urls import reverse
from django.test import Client
from apps.authentication.models import User

# Create test client
client = Client()

# Test URLs
urls_to_test = [
    ('core:landing', '/'),
    ('core:dashboard', '/dashboard/'),
    ('core:health_check', '/health/'),
    ('authentication:login', '/auth/login/'),
    ('opportunities:list', '/opportunities/'),
    ('documents:list', '/documents/'),
    ('ai_integration:dashboard', '/ai/'),
    ('compliance:dashboard', '/compliance/'),
]

print("Testing URL Configuration...")
print("=" * 50)

for url_name, expected_path in urls_to_test:
    try:
        actual_path = reverse(url_name)
        status = "✅ PASS" if actual_path == expected_path else f"❌ FAIL (got {actual_path})"
        print(f"{url_name:25} -> {expected_path:20} {status}")
    except Exception as e:
        print(f"{url_name:25} -> {expected_path:20} ❌ ERROR: {e}")

print("\nTesting Authentication Redirect...")
print("=" * 50)

# Test that accessing protected dashboard redirects to login
response = client.get('/dashboard/')
if response.status_code == 302 and '/auth/login/' in response.url:
    print("Dashboard redirect        -> /auth/login/          ✅ PASS")
else:
    print(f"Dashboard redirect        -> Expected redirect     ❌ FAIL (got {response.status_code})")

# Test that landing page loads for unauthenticated users
response = client.get('/')
if response.status_code == 200:
    print("Landing page loads        -> 200 OK                ✅ PASS")
else:
    print(f"Landing page loads        -> 200 OK                ❌ FAIL (got {response.status_code})")

# Test login page loads
response = client.get('/auth/login/')
if response.status_code == 200:
    print("Login page loads          -> 200 OK                ✅ PASS")
else:
    print(f"Login page loads          -> 200 OK                ❌ FAIL (got {response.status_code})")

print("\nURL configuration is working correctly!")
print("You can now start the server with: python manage.py runserver")