#!/bin/bash

# AI Chatbot Startup Script for Vast.ai
# This script sets up and runs the chatbot application

echo "=================================="
echo "AI Chatbot Deployment on Vast.ai"
echo "=================================="

# Create necessary directories
mkdir -p logs
mkdir -p data/knowledge

# Set environment variables if not already set
export PORT=${PORT:-5000}
export FLASK_ENV=production

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Please edit .env file with your actual credentials!"
    fi
fi

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Initialize the chatbot (if needed)
echo "Initializing chatbot and RAG system..."
python -c "from app import initialize_chatbot; initialize_chatbot()" || echo "Initialization will happen on first request"

# Start the application with Gunicorn
echo "Starting Gunicorn server on port $PORT..."
gunicorn -c gunicorn_config.py app:app

# Alternative: Use Flask development server (not recommended for production)
# python app.py
