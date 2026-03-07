#!/bin/bash
# Paste this entire script on your Linux server and run it
# This will fix the /test route directly on the server

echo "🔧 Fixing /test route on server..."

cd /root/ai_services/ai_chatbot

# Backup original file
cp src/api/app_simple.py src/api/app_simple.py.backup

# Fix the imports - add send_from_directory
sed -i 's/from flask import Flask, request, jsonify$/from flask import Flask, request, jsonify, send_from_directory/' src/api/app_simple.py

# Add static folder configuration after logging setup
# Find the line with "app = Flask(__name__)" and replace it
sed -i '/^app = Flask(__name__)$/i # Get project root\nPROJECT_ROOT = os.path.join(os.path.dirname(__file__), '"'"'..'"'"', '"'"'..'"'"')\nSTATIC_FOLDER = os.path.join(PROJECT_ROOT, '"'"'static'"'"')\n' src/api/app_simple.py
sed -i 's/^app = Flask(__name__)$/app = Flask(__name__, static_folder=STATIC_FOLDER)/' src/api/app_simple.py

# Fix the /test route to accept GET and POST
sed -i "s/@app.route('\/test', methods=\['POST'\])/@app.route('\/test', methods=['GET', 'POST'])/" src/api/app_simple.py

# Replace the test function
cat > /tmp/test_function.txt << 'EOF'
@app.route('/test', methods=['GET', 'POST'])
def test():
    """Test endpoint - GET for chat interface, POST same as /chat"""
    if request.method == 'GET':
        return send_from_directory(STATIC_FOLDER, 'chat.html')
    return chat()
EOF

# Use Python to do the replacement properly
python3 << 'PYTHON_SCRIPT'
import re

with open('src/api/app_simple.py', 'r') as f:
    content = f.read()

# Replace the test function
pattern = r'@app\.route\(\'/test\',.*?\)\s*def test\(\):.*?return chat\(\)'
replacement = """@app.route('/test', methods=['GET', 'POST'])
def test():
    \"\"\"Test endpoint - GET for chat interface, POST same as /chat\"\"\"
    if request.method == 'GET':
        return send_from_directory(STATIC_FOLDER, 'chat.html')
    return chat()"""

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('src/api/app_simple.py', 'w') as f:
    f.write(content)

print("✅ File updated successfully")
PYTHON_SCRIPT

echo ""
echo "✅ Code fixed!"
echo ""
echo "Now restarting server..."

# Stop gunicorn
pkill -f gunicorn
sleep 2

# Start gunicorn
echo "🚀 Starting Gunicorn..."
gunicorn -c config/gunicorn_config.py src.api.app_simple:app &

sleep 3

echo ""
echo "================================================"
echo "✅ Server Updated and Restarted!"
echo "================================================"
echo ""
echo "🌐 Test your chat interface at:"
echo "   http://128.199.144.145:5000/test"
echo ""
echo "📋 Backup saved at: src/api/app_simple.py.backup"
echo "================================================"
