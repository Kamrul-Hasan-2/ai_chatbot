#!/bin/bash
# AI Template Endpoint - Testing Examples
# Complete reference guide for testing the /api/item/ai_template/ endpoint

# Base URL (adjust based on your deployment)
BASE_URL="http://localhost:5000"
API_KEY="mkh677ddd2sxxk"

echo "=================================="
echo "AI Template Endpoint - Test Examples"
echo "=================================="

# Test 1: Search for "Laptop" category
echo -e "\n[TEST 1] Search for Laptop category"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=Laptop&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=Laptop&key=$API_KEY" | jq .

# Test 2: Search for "Desktop PC" category
echo -e "\n[TEST 2] Search for Desktop PC category"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=Desktop%20PC&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=Desktop%20PC&key=$API_KEY" | jq .

# Test 3: Search for "Used Laptop" category
echo -e "\n[TEST 3] Search for Used Laptop category"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=Used%20Laptop&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=Used%20Laptop&key=$API_KEY" | jq .

# Test 4: Search for "Mouse" category
echo -e "\n[TEST 4] Search for Mouse category"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=Mouse&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=Mouse&key=$API_KEY" | jq .

# Test 5: Search for "Mobile Phone" category
echo -e "\n[TEST 5] Search for Mobile Phone category"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=Mobile%20Phone&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=Mobile%20Phone&key=$API_KEY" | jq .

# Test 6: Invalid category (should fail)
echo -e "\n[TEST 6] Invalid category - should return 404"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=InvalidCategory123&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=InvalidCategory123&key=$API_KEY" | jq .

# Test 7: Invalid API key (should fail)
echo -e "\n[TEST 7] Invalid API key - should return 401"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=Laptop&key=invalid_key_123"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=Laptop&key=invalid_key_123" | jq .

# Test 8: Missing category parameter (should fail)
echo -e "\n[TEST 8] Missing category parameter - should return 400"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&key=$API_KEY" | jq .

# Test 9: Invalid intent (should fail)
echo -e "\n[TEST 9] Invalid intent - should return 400"
echo "URL: $BASE_URL/api/item/ai_template/?intent=invalid&category=Laptop&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=invalid&category=Laptop&key=$API_KEY" | jq .

# Test 10: Case-insensitive search (lowercase "laptop")
echo -e "\n[TEST 10] Case-insensitive - lowercase 'laptop'"
echo "URL: $BASE_URL/api/item/ai_template/?intent=category&category=laptop&key=$API_KEY"
curl -s "$BASE_URL/api/item/ai_template/?intent=category&category=laptop&key=$API_KEY" | jq .

echo -e "\n=================================="
echo "All tests completed!"
echo "==================================\n"
