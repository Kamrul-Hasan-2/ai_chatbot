# AI Template Endpoint - Testing Examples (PowerShell)
# Complete reference guide for testing the /api/item/ai_template/ endpoint on Windows

# Base URL (adjust based on your deployment)
$BASE_URL = "http://localhost:5000"
$API_KEY = "mkh677ddd2sxxk"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "AI Template Endpoint - Test Examples" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Test 1: Search for "Laptop" category
Write-Host "`n[TEST 1] Search for Laptop category" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=Laptop&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
$response = Invoke-RestMethod -Uri $url -Method Get
Write-Host "Response:" -ForegroundColor Green
$response | ConvertTo-Json | Write-Host

# Test 2: Search for "Desktop PC" category
Write-Host "`n[TEST 2] Search for Desktop PC category" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=Desktop%20PC&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
$response = Invoke-RestMethod -Uri $url -Method Get
Write-Host "Response:" -ForegroundColor Green
$response | ConvertTo-Json | Write-Host

# Test 3: Search for "Used Laptop" category
Write-Host "`n[TEST 3] Search for Used Laptop category" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=Used%20Laptop&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
$response = Invoke-RestMethod -Uri $url -Method Get
Write-Host "Response:" -ForegroundColor Green
$response | ConvertTo-Json | Write-Host

# Test 4: Search for "Mouse" category
Write-Host "`n[TEST 4] Search for Mouse category" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=Mouse&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
$response = Invoke-RestMethod -Uri $url -Method Get
Write-Host "Response:" -ForegroundColor Green
$response | ConvertTo-Json | Write-Host

# Test 5: Search for "Mobile Phone" category
Write-Host "`n[TEST 5] Search for Mobile Phone category" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=Mobile%20Phone&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
$response = Invoke-RestMethod -Uri $url -Method Get
Write-Host "Response:" -ForegroundColor Green
$response | ConvertTo-Json | Write-Host

# Test 6: Invalid category (should fail with 404)
Write-Host "`n[TEST 6] Invalid category - should return 404" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=InvalidCategory123&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri $url -Method Get
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json | Write-Host
} catch {
    Write-Host "Error (Expected):" -ForegroundColor Red
    $_.Exception.Message | Write-Host
}

# Test 7: Invalid API key (should fail with 401)
Write-Host "`n[TEST 7] Invalid API key - should return 401" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=Laptop&key=invalid_key_123"
Write-Host "URL: $url" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri $url -Method Get
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json | Write-Host
} catch {
    Write-Host "Error (Expected):" -ForegroundColor Red
    $_.Exception.Message | Write-Host
}

# Test 8: Missing category parameter (should fail with 400)
Write-Host "`n[TEST 8] Missing category parameter - should return 400" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri $url -Method Get
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json | Write-Host
} catch {
    Write-Host "Error (Expected):" -ForegroundColor Red
    $_.Exception.Message | Write-Host
}

# Test 9: Invalid intent (should fail with 400)
Write-Host "`n[TEST 9] Invalid intent - should return 400" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=invalid&category=Laptop&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri $url -Method Get
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json | Write-Host
} catch {
    Write-Host "Error (Expected):" -ForegroundColor Red
    $_.Exception.Message | Write-Host
}

# Test 10: Case-insensitive search (lowercase "laptop")
Write-Host "`n[TEST 10] Case-insensitive - lowercase 'laptop'" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=laptop&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
$response = Invoke-RestMethod -Uri $url -Method Get
Write-Host "Response:" -ForegroundColor Green
$response | ConvertTo-Json | Write-Host

# Test 11: Category with special characters/spaces
Write-Host "`n[TEST 11] Category with multiple words - 'laptop under 10k'" -ForegroundColor Yellow
$url = "$BASE_URL/api/item/ai_template/?intent=category&category=laptop%20under%2010k&key=$API_KEY"
Write-Host "URL: $url" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri $url -Method Get
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json | Write-Host
} catch {
    Write-Host "Error:" -ForegroundColor Red
    $_.Exception.Message | Write-Host
}

Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host "All tests completed!" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
