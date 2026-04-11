"""
Test AI Template Endpoint
Tests the new /api/item/ai_template/ endpoint for category search
"""
import sys
import os
import json

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test with Flask client
from src.api.app_simple import app

def test_ai_template_endpoint():
    """Test the AI template endpoint with various scenarios"""
    
    client = app.test_client()
    
    print("\n" + "="*70)
    print("Testing AI Template Endpoint")
    print("="*70)
    
    # Test 1: Valid category - "Laptop"
    print("\n[TEST 1] Valid category: 'Laptop'")
    response = client.get('/api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 200
    assert response.get_json()['success'] == True
    assert 'Laptop' in response.get_json()['data'] or 'laptop' in response.get_json()['data'].lower()
    print("✅ PASSED")
    
    # Test 2: Valid category - "laptop" (lowercase)
    print("\n[TEST 2] Valid category: 'laptop' (lowercase)")
    response = client.get('/api/item/ai_template/?intent=category&category=laptop&key=mkh677ddd2sxxk')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 200
    assert response.get_json()['success'] == True
    print("✅ PASSED")
    
    # Test 3: Valid category - "Desktop PC"
    print("\n[TEST 3] Valid category: 'Desktop PC'")
    response = client.get('/api/item/ai_template/?intent=category&category=Desktop%20PC&key=mkh677ddd2sxxk')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 200
    assert response.get_json()['success'] == True
    print("✅ PASSED")
    
    # Test 4: Invalid category
    print("\n[TEST 4] Invalid category: 'invalid_category_xyz'")
    response = client.get('/api/item/ai_template/?intent=category&category=invalid_category_xyz&key=mkh677ddd2sxxk')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 404
    assert response.get_json()['success'] == False
    print("✅ PASSED")
    
    # Test 5: Invalid API key
    print("\n[TEST 5] Invalid API key")
    response = client.get('/api/item/ai_template/?intent=category&category=laptop&key=invalid_key')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 401
    assert response.get_json()['success'] == False
    print("✅ PASSED")
    
    # Test 6: Missing category parameter
    print("\n[TEST 6] Missing category parameter")
    response = client.get('/api/item/ai_template/?intent=category&key=mkh677ddd2sxxk')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 400
    assert response.get_json()['success'] == False
    print("✅ PASSED")
    
    # Test 7: Invalid intent
    print("\n[TEST 7] Invalid intent")
    response = client.get('/api/item/ai_template/?intent=invalid&category=laptop&key=mkh677ddd2sxxk')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.get_json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 400
    print("✅ PASSED")
    
    # Test 8: Valid category check URL format
    print("\n[TEST 8] Verify URL format in response")
    response = client.get('/api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk')
    data = response.get_json()
    assert 'https://www.bdstall.com' in data['data']
    print(f"Response data: {data['data']}")
    print("✅ PASSED")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70 + "\n")


if __name__ == '__main__':
    test_ai_template_endpoint()
