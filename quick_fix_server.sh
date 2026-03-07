#!/bin/bash
# Simple fix - just restart with the correct Python code inline

echo "🔧 Quick Fix for /test route"
echo ""

cd /root/ai_services/ai_chatbot

# Stop current server
echo "⏹️ Stopping current server..."
pkill -f gunicorn
sleep 2

# Create a quick patch file
cat > /tmp/fix_test_route.py << 'ENDPYTHON'
import sys
import os

file_path = '/root/ai_services/ai_chatbot/src/api/app_simple.py'

print("Reading file...")
with open(file_path, 'r') as f:
    content = f.read()

# Fix 1: Add send_from_directory to imports if not there
if 'send_from_directory' not in content:
    content = content.replace(
        'from flask import Flask, request, jsonify',
        'from flask import Flask, request, jsonify, send_from_directory'
    )
    print("✓ Added send_from_directory import")

# Fix 2: Add static folder config if not there
if 'STATIC_FOLDER' not in content:
    # Find where to insert
    if "app = Flask(__name__)" in content and "static_folder" not in content:
        old = "app = Flask(__name__)"
        new = """# Get project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'static')

# Initialize Flask
app = Flask(__name__, static_folder=STATIC_FOLDER)"""
        content = content.replace(old, new)
        print("✓ Added static folder configuration")

# Fix 3: Fix the /test route
old_test = '''@app.route('/test', methods=['POST'])
def test():
    """Test endpoint - same as /chat"""
    return chat()'''

new_test = '''@app.route('/test', methods=['GET', 'POST'])
def test():
    """Test endpoint - GET for chat interface, POST same as /chat"""
    if request.method == 'GET':
        return send_from_directory(STATIC_FOLDER, 'chat.html')
    return chat()'''

if old_test in content:
    content = content.replace(old_test, new_test)
    print("✓ Fixed /test route")
elif "methods=['POST']" in content and "def test():" in content:
    # Try alternative matching
    import re
    pattern = r"@app\.route\('/test',\s*methods=\['POST'\]\)\s*def test\(\):\s*\"\"\".*?\"\"\"\s*return chat\(\)"
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_test, content, flags=re.DOTALL)
        print("✓ Fixed /test route (alternative)")

# Write back
with open(file_path, 'w') as f:
    f.write(content)

print("✅ All fixes applied!")
ENDPYTHON

echo "Applying fixes..."
python3 /tmp/fix_test_route.py

echo ""
echo "🚀 Starting server..."
gunicorn -c config/gunicorn_config.py src.api.app_simple:app &

sleep 3

echo ""
echo "================================================"
echo "✅ Server Fixed and Running!"
echo "================================================"
echo "🌐 Chat Interface: http://128.199.144.145:5000/test"
echo "================================================"
