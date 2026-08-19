"""
Test script for EcoPulse API endpoints.
Tests both backend endpoints and frontend integration.
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_endpoint(method, path, data=None, headers=None, expected_status=200):
    """Generic test function for endpoints."""
    url = f"{BASE_URL}{path}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        else:
            return False, f"Unknown method: {method}"
        
        success = response.status_code == expected_status
        status_icon = GREEN + "✓" + RESET if success else RED + "✗" + RESET
        
        print(f"{status_icon} {method} {path}")
        print(f"  Status: {response.status_code} (expected {expected_status})")
        
        try:
            response_data = response.json()
            print(f"  Response: {json.dumps(response_data, indent=2)[:200]}...")
        except:
            print(f"  Response: {response.text[:200]}")
        
        return success, response
        
    except Exception as e:
        print(f"{RED}✗{RESET} {method} {path}")
        print(f"  Error: {str(e)}")
        return False, None


def main():
    print(f"\n{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}EcoPulse API Integration Tests{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}\n")
    
    results = {
        "health": False,
        "cloud_providers": False,
        "iam_policy": False,
        "access_checklist": False,
    }
    
    # Test 1: Health Check
    print(f"\n{YELLOW}1. Testing Health Check{RESET}")
    success, response = test_endpoint("GET", "/health")
    results["health"] = success
    
    # Test 2: List Cloud Providers
    print(f"\n{YELLOW}2. Testing Cloud Providers Endpoint{RESET}")
    success, response = test_endpoint("GET", "/auth/cloud-providers")
    results["cloud_providers"] = success
    if response and success:
        data = response.json()
        print(f"  Providers: {len(data)} available")
    
    # Test 3: Get IAM Policy for AWS
    print(f"\n{YELLOW}3. Testing IAM Policy Endpoint (AWS){RESET}")
    success, response = test_endpoint("GET", "/auth/onboarding/iam-policy?provider=aws")
    results["iam_policy"] = success
    if response and success:
        data = response.json()
        print(f"  Policy Statements: {len(data.get('Statement', []))} statement(s)")
    
    # Test 4: Get Access Checklist
    print(f"\n{YELLOW}4. Testing Access Checklist Endpoint (AWS){RESET}")
    success, response = test_endpoint("GET", "/auth/onboarding/access-checklist?provider=aws")
    results["access_checklist"] = success
    if response and success:
        data = response.json()
        print(f"  Checklist Items: {len(data)} item(s)")
    
    # Test 5: Create test organization for further testing
    print(f"\n{YELLOW}5. Testing Signup Endpoint{RESET}")
    signup_data = {
        "email": f"test-{int(time.time())}@example.com",
        "password": "TestPassword123!",
        "org_name": "Test Organization",
        "full_name": "Test User"
    }
    success, response = test_endpoint("POST", "/auth/signup", data=signup_data)
    
    org_id = None
    user_id = None
    if response and success:
        data = response.json()
        org_id = data.get("org_id")
        user_id = data.get("user_id")
        print(f"  Organization ID: {org_id}")
        print(f"  User ID: {user_id}")
    
    # Test 6-10: Waste Analytics Endpoints (only if org created)
    if org_id:
        print(f"\n{YELLOW}6. Testing Dashboard Stats Endpoint{RESET}")
        success, response = test_endpoint(
            "GET", 
            f"/waste-analytics/dashboard/stats?org_id={org_id}",
            expected_status=200
        )
        results["dashboard_stats"] = success
        
        print(f"\n{YELLOW}7. Testing Cost Trend Endpoint{RESET}")
        success, response = test_endpoint(
            "GET", 
            f"/waste-analytics/analytics/cost-trend?org_id={org_id}&days=30",
            expected_status=200
        )
        results["cost_trend"] = success
        if response and success:
            data = response.json()
            print(f"  Data Points: {len(data)} day(s)")
        
        print(f"\n{YELLOW}8. Testing Waste Items Endpoint{RESET}")
        success, response = test_endpoint(
            "GET",
            f"/waste-analytics/items?org_id={org_id}&min_severity=0.0&limit=10",
            expected_status=200
        )
        results["waste_items"] = success
        if response and success:
            data = response.json()
            print(f"  Waste Items: {len(data)} item(s)")
        
        print(f"\n{YELLOW}9. Testing Waste Summary Endpoint{RESET}")
        success, response = test_endpoint(
            "GET",
            f"/waste-analytics/summary?org_id={org_id}",
            expected_status=200
        )
        results["waste_summary"] = success
        
        print(f"\n{YELLOW}10. Testing Insights by Service Endpoint{RESET}")
        success, response = test_endpoint(
            "GET",
            f"/waste-analytics/insights/by-service?org_id={org_id}",
            expected_status=200
        )
        results["insights_service"] = success
        if response and success:
            data = response.json()
            print(f"  Services: {len(data)} service(s)")
        
        print(f"\n{YELLOW}11. Testing Remediation History Endpoint{RESET}")
        success, response = test_endpoint(
            "GET",
            f"/waste-analytics/recommendations/history?org_id={org_id}&limit=10",
            expected_status=200
        )
        results["remediation_history"] = success
        if response and success:
            data = response.json()
            print(f"  Actions: {len(data)} action(s)")
        
        # Test Get Current User
        print(f"\n{YELLOW}12. Testing Get Current User Endpoint{RESET}")
        if user_id:
            success, response = test_endpoint(
                "GET",
                f"/auth/me?user_id={user_id}",
                expected_status=200
            )
            results["current_user"] = success
    
    # Summary
    print(f"\n{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}Test Summary{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for endpoint, result in results.items():
        status = GREEN + "PASS" + RESET if result else RED + "FAIL" + RESET
        print(f"{status} - {endpoint}")
    
    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"{GREEN}✓ All endpoints working correctly!{RESET}\n")
    else:
        print(f"{RED}✗ Some endpoints failed. Check the details above.{RESET}\n")


if __name__ == "__main__":
    main()
