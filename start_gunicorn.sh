#!/bin/bash

# Quick Start with Gunicorn (without systemd)
# Use this for testing or if you prefer manual control

echo "🤖 Starting AI Chatbot with Gunicorn..."
echo "================================================"

# Navigate to app directory
cd /root/ai_services/ai_chatbot

# Create logs directory
mkdir -p logs

# Kill any existing Flask development servers
pkill -f "flask run" || true
pkill -f "python run.py" || true

# Start with Gunicorn
echo "🚀 Starting Gunicorn on 0.0.0.0:5000..."
gunicorn -c config/gunicorn_config.py src.api.app_simple:app

# Note: This will run in foreground. Press CTRL+C to stop.
# To run in background, add '&' at the end:
# gunicorn -c config/gunicorn_config.py src.api.app_simple:app &
