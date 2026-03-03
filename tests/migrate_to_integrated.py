"""
Migration Script: Upgrade to BDStall Chatbot System
This script helps transition from the old chatbot to the new architectural system
"""
import os
import shutil
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backup_existing_files():
    """Backup existing files before migration"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    
    logger.info(f"Creating backup directory: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Files to backup
    files_to_backup = [
        "app.py",
        "chatbot.py",
        "requirements.txt"
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy2(file, os.path.join(backup_dir, file))
            logger.info(f"✓ Backed up: {file}")
    
    return backup_dir


def migrate_to_integrated_system():
    """Migrate to the new integrated system"""
    logger.info("Starting migration to BDStall Chatbot System...")
    
    # Step 1: Backup existing files
    backup_dir = backup_existing_files()
    
    # Step 2: Replace app.py with integrated version
    if os.path.exists("app_integrated.py"):
        logger.info("Replacing app.py with integrated version...")
        
        # Backup current app.py if it exists
        if os.path.exists("app.py"):
            shutil.move("app.py", os.path.join(backup_dir, "app_original.py"))
        
        # Copy integrated version
        shutil.copy2("app_integrated.py", "app.py")
        logger.info("✓ app.py updated with new integrated system")
    
    # Step 3: Update requirements if needed
    new_requirements = """
# Existing requirements
flask==2.3.2
flask-cors==4.0.0
requests==2.31.0
python-dotenv==1.0.0
gunicorn==21.2.0

# New system requirements
dataclasses-json==0.6.1
typing-extensions==4.7.1
"""
    
    logger.info("Updating requirements...")
    with open("requirements_new.txt", "w", encoding="utf-8") as f:
        f.write(new_requirements)
    logger.info("✓ Created requirements_new.txt")
    
    # Step 4: Create migration verification script
    create_verification_script()
    
    logger.info("=" * 60)
    logger.info("🎉 Migration completed successfully!")
    logger.info("=" * 60)
    logger.info("Next steps:")
    logger.info("1. Install new requirements: pip install -r requirements_new.txt")
    logger.info("2. Test the system: python test_migration.py")
    logger.info("3. Start the server: python app.py")
    logger.info(f"4. Original files backed up to: {backup_dir}/")
    logger.info("=" * 60)


def create_verification_script():
    """Create a script to verify the migration"""
    verification_script = '''"""
Migration Verification Script
Tests the new BDStall Chatbot System integration
"""
import requests
import json
import time


def test_endpoints():
    """Test all endpoints to ensure they work"""
    base_url = "http://localhost:8000"
    tests_passed = 0
    tests_failed = 0
    
    print("🧪 Testing BDStall Chatbot System Integration")
    print("=" * 50)
    
    # Test 1: Health Check
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health check - PASSED")
            tests_passed += 1
        else:
            print("❌ Health check - FAILED")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Health check - ERROR: {e}")
        tests_failed += 1
    
    # Test 2: System Health
    try:
        response = requests.get(f"{base_url}/system_health")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ System health - PASSED ({health_data['status']})")
            tests_passed += 1
        else:
            print("❌ System health - FAILED")
            tests_failed += 1
    except Exception as e:
        print(f"❌ System health - ERROR: {e}")
        tests_failed += 1
    
    # Test 3: Test Message
    try:
        test_data = {
            "user_id": "migration_test",
            "message": "Hello, testing new system!"
        }
        response = requests.post(f"{base_url}/test", json=test_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Test message - PASSED")
            print(f"  Response: {result.get('response', 'No response')[:50]}...")
            tests_passed += 1
        else:
            print("❌ Test message - FAILED")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Test message - ERROR: {e}")
        tests_failed += 1
    
    # Test 4: Chat Endpoint
    try:
        chat_data = {
            "user_id": "migration_chat_test",
            "message": "What products do you have?"
        }
        response = requests.post(f"{base_url}/chat", json=chat_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Chat endpoint - PASSED")
            tests_passed += 1
        else:
            print("❌ Chat endpoint - FAILED")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Chat endpoint - ERROR: {e}")
        tests_failed += 1
    
    # Test 5: Process Endpoint (New)
    try:
        process_data = {
            "user_id": "migration_process_test",
            "message": "Tell me about your services",
            "channel": "api"
        }
        response = requests.post(f"{base_url}/process", json=process_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Process endpoint - PASSED")
            print(f"  Processing info available: {'processing_info' in result}")
            tests_passed += 1
        else:
            print("❌ Process endpoint - FAILED")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Process endpoint - ERROR: {e}")
        tests_failed += 1
    
    print("=" * 50)
    print(f"📊 Test Results: {tests_passed} passed, {tests_failed} failed")
    
    if tests_failed == 0:
        print("🎉 All tests passed! Migration successful.")
        return True
    else:
        print(f"⚠️  {tests_failed} tests failed. Check the logs.")
        return False


def test_architectural_components():
    """Test that all architectural components are working"""
    print("\\n🏗️  Testing Architectural Components")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Test system health to see component status
    try:
        response = requests.get(f"{base_url}/system_health")
        if response.status_code == 200:
            health = response.json()
            components = health.get("components", {})
            
            expected_components = [
                "Channel Adapter",
                "Intent & Entity Detector", 
                "Context Router",
                "Business Rule Engine",
                "Decision Router",
                "Response Composer"
            ]
            
            for component in expected_components:
                status = components.get(component, "Not Found")
                if status == "healthy":
                    print(f"✓ {component} - HEALTHY")
                else:
                    print(f"❌ {component} - {status}")
        
        print("=" * 50)
        
    except Exception as e:
        print(f"Error testing components: {e}")


if __name__ == "__main__":
    print("Starting migration verification...")
    print("Make sure the server is running: python app.py")
    print()
    
    # Wait a moment for manual server startup
    input("Press Enter when the server is running...")
    
    # Run tests
    success = test_endpoints()
    test_architectural_components()
    
    if success:
        print("\\n🚀 Migration verification completed successfully!")
        print("Your BDStall Chatbot System is ready to use!")
    else:
        print("\\n⚠️  Some issues detected. Please check the server logs.")
'''
    
    with open("test_migration.py", "w", encoding="utf-8") as f:
        f.write(verification_script)
    
    logger.info("✓ Created migration verification script: test_migration.py")


if __name__ == "__main__":
    print("🔄 BDStall Chatbot System Migration")
    print("=" * 60)
    print("This will upgrade your chatbot to the new architectural system.")
    print("Your existing files will be backed up automatically.")
    print()
    
    response = input("Do you want to proceed with migration? (y/N): ")
    
    if response.lower() in ['y', 'yes']:
        migrate_to_integrated_system()
    else:
        print("Migration cancelled.")