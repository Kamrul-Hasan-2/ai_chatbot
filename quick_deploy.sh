#!/bin/bash

#############################################
# ONE-COMMAND DEPLOYMENT
# Run this on your server to deploy everything
#############################################

echo "🚀 AI Chatbot - One Command Deployment"
echo "========================================"

# Stop current Flask dev server
echo "⏹️  Stopping Flask development server..."
pkill -f "python run.py" || pkill -f "flask run" || true

# Wait 2 seconds
sleep 2

# Start with Gunicorn
echo "🚀 Starting with Gunicorn..."
cd /root/ai_services/ai_chatbot
gunicorn -c config/gunicorn_config.py src.api.app_simple:app

# This runs in foreground - press CTRL+C to stop

