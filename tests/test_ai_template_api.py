#!/usr/bin/env python3
"""
Test script for AI Template Intent/Category Search API
Tests the new /api/item/ai_template endpoint
"""

import requests
import json
import sys
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

# Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "mkh677ddd2sxxk"

def test_category_found():
    """Test when category is found"""
    print(f"\n{Fore.BLUE}Test 1: Category Found (Laptop){Style.RESET_ALL}")
    
    url = f"{API_BASE_URL}/api/item/ai_template"
    params = {
        "intent": "category",
        "category": "Laptop",
        "key": API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 200, "Expected 200, got " + str(response.status_code)
        assert data["success"] == True, "Expected success=true"
        assert data["category"] == "Laptop", "Expected category=Laptop"
        assert "laptop" in data["url"].lower(), "Expected URL to contain 'laptop'"
        
        print(f"{Fore.GREEN}✓ Test PASSED{Style.RESET_ALL}")
        return True
        
    except Exception as e:
        print(f"{Fore.RED}✗ Test FAILED: {e}{Style.RESET_ALL}")
        return False


def test_category_case_insensitive():
    """Test case-insensitive search"""
    print(f"\n{Fore.BLUE}Test 2: Case-Insensitive Search (laptop, LAPTOP, LaPtOp){Style.RESET_ALL}")
    
    test_cases = ["laptop", "LAPTOP", "LaPtOp", "LaPhot"]
    
    for category in test_cases:
        url = f"{API_BASE_URL}/api/item/ai_template"
        params = {
            "intent": "category",
            "category": category,
            "key": API_KEY
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if category.lower() == "laptop":
                assert data["success"] == True, f"Expected success for {category}"
                print(f"  ✓ {category}: Found")
            
        except Exception as e:
            print(f"  ✗ {category}: {e}")
            return False
    
    print(f"{Fore.GREEN}✓ Test PASSED{Style.RESET_ALL}")
    return True


def test_category_not_found():
    """Test when category is not found"""
    print(f"\n{Fore.BLUE}Test 3: Category Not Found (XYZ1234NonExistent){Style.RESET_ALL}")
    
    url = f"{API_BASE_URL}/api/item/ai_template"
    params = {
        "intent": "category",
        "category": "XYZ1234NonExistent",
        "key": API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 404, "Expected 404, got " + str(response.status_code)
        assert data["success"] == False, "Expected success=false"
        assert data["error"] is not None, "Expected error message"
        
        print(f"{Fore.GREEN}✓ Test PASSED{Style.RESET_ALL}")
        return True
        
    except Exception as e:
        print(f"{Fore.RED}✗ Test FAILED: {e}{Style.RESET_ALL}")
        return False


def test_missing_parameters():
    """Test when parameters are missing"""
    print(f"\n{Fore.BLUE}Test 4: Missing Parameters{Style.RESET_ALL}")
    
    # Missing category
    url = f"{API_BASE_URL}/api/item/ai_template"
    params = {
        "intent": "category",
        "key": API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 400, "Expected 400, got " + str(response.status_code)
        assert data["success"] == False, "Expected success=false"
        
        print(f"{Fore.GREEN}✓ Test PASSED{Style.RESET_ALL}")
        return True
        
    except Exception as e:
        print(f"{Fore.RED}✗ Test FAILED: {e}{Style.RESET_ALL}")
        return False


def test_multiple_categories():
    """Test multiple valid categories"""
    print(f"\n{Fore.BLUE}Test 5: Multiple Valid Categories{Style.RESET_ALL}")
    
    categories = [
        "Laptop",
        "Desktop PC",
        "Monitor",
        "Printer",
        "Keyboard",
        "Mouse",
        "Graphics Card"
    ]
    
    failed = []
    for category in categories:
        url = f"{API_BASE_URL}/api/item/ai_template"
        params = {
            "intent": "category",
            "category": category,
            "key": API_KEY
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data["success"]:
                print(f"  ✓ {category}")
            else:
                print(f"  ✗ {category}: Not found")
                failed.append(category)
                
        except Exception as e:
            print(f"  ✗ {category}: {e}")
            failed.append(category)
    
    if not failed:
        print(f"{Fore.GREEN}✓ Test PASSED{Style.RESET_ALL}")
        return True
    else:
        print(f"{Fore.RED}✗ Test FAILED: {len(failed)} categories failed{Style.RESET_ALL}")
        return False


def test_bengali_response():
    """Test that response contains Bengali text"""
    print(f"\n{Fore.BLUE}Test 6: Bengali Response Text{Style.RESET_ALL}")
    
    url = f"{API_BASE_URL}/api/item/ai_template"
    params = {
        "intent": "category",
        "category": "Laptop",
        "key": API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data["success"]:
            bengali_text = data["data"]
            print(f"Response: {bengali_text}")
            
            # Check for Bengali characters
            has_bengali = any('\u0980' <= char <= '\u09FF' for char in bengali_text)
            
            assert has_bengali, "Response doesn't contain Bengali text"
            assert "https://www.bdstall.com/" in bengali_text, "Response doesn't contain BDStall URL"
            
            print(f"{Fore.GREEN}✓ Test PASSED{Style.RESET_ALL}")
            return True
        else:
            raise Exception("Category not found")
            
    except Exception as e:
        print(f"{Fore.RED}✗ Test FAILED: {e}{Style.RESET_ALL}")
        return False


def main():
    """Run all tests"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print("AI Template Intent/Category Search API - Test Suite")
    print(f"{'='*60}{Style.RESET_ALL}")
    
    tests = [
        test_category_found,
        test_category_case_insensitive,
        test_category_not_found,
        test_missing_parameters,
        test_multiple_categories,
        test_bengali_response
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"{Fore.RED}✗ Test {test_func.__name__} failed with exception: {e}{Style.RESET_ALL}")
            results.append(False)
    
    # Summary
    print(f"\n{Fore.CYAN}{'='*60}")
    print("Test Summary")
    print(f"{'='*60}{Style.RESET_ALL}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Total: {total}")
    print(f"Passed: {Fore.GREEN}{passed}{Style.RESET_ALL}")
    print(f"Failed: {Fore.RED}{total - passed}{Style.RESET_ALL}")
    
    if passed == total:
        print(f"\n{Fore.GREEN}All tests passed! ✓{Style.RESET_ALL}")
        return 0
    else:
        print(f"\n{Fore.RED}Some tests failed! ✗{Style.RESET_ALL}")
        return 1


if __name__ == "__main__":
    print("\n⚠️  Make sure the Flask server is running on http://localhost:8000")
    print("   Run: python run.py\n")
    
    sys.exit(main())
