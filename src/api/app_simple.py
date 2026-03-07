"""
Simple API - Following Your Roadmap
Cleaner, simpler implementation
"""
import os
import sys
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import simple chatbot
from core.simple_chatbot_flow import SimpleChatbot

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'static')

# Initialize Flask
app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

# Initialize chatbot
chatbot = None


@app.route('/', methods=['GET'])
def index():
    """API Info"""
    return jsonify({
        "service": "Simple Chatbot API",
        "version": "1.0",
        "roadmap": {
            "step_1": "Message → Groq API (Intent Detection)",
            "step_2": "Intent → Search API",
            "step_3": "Results → Database Format",
            "step_4": "Database → AI Formatting",
            "step_5": "Track AI/HUMAN mode",
            "step_6": "Return JSON with mode"
        },
        "endpoints": {
            "/chat": "POST - Send message",
            "/health": "GET - Health check",
            "/mode/:user_id": "GET - Get user mode",
            "/mode/:user_id/human": "POST - Switch to human",
            "/mode/:user_id/ai": "POST - Switch to AI",
            "/test": "GET - Chat interface (web), POST - Send message"
        }
    }), 200


@app.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint
    
    Request:
    {
        "user_id": "user123",
        "message": "amake ekta 10k er modde laptop dekhan"
    }
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "message": "...",
        "response": "...",
        "mode": "ai",  ← Always shows: "ai" or "human"
        "intent": "laptop_search",
        "products_found": 3,
        "products": [...]
    }
    """
    try:
        data = request.get_json()
        
        user_id = data.get('user_id', 'web_user')
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                "success": False,
                "error": "No message provided",
                "mode": "ai"
            }), 400
        
        # Process message through roadmap
        result = chatbot.process_message(user_id, message)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "response": "দুঃখিত, কিছু সমস্যা হয়েছে।",
            "mode": "human"
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "chatbot_loaded": chatbot is not None,
        "api_configured": bool(chatbot.api_url) if chatbot else False,
        "database_responses": len(chatbot.database) if chatbot else 0,
        "groq_available": chatbot.groq_client is not None if chatbot else False
    }), 200


@app.route('/mode/<user_id>', methods=['GET'])
def get_mode(user_id):
    """Get current mode for user"""
    mode = chatbot.get_user_mode(user_id)
    return jsonify({
        "user_id": user_id,
        "mode": mode
    }), 200


@app.route('/mode/<user_id>/human', methods=['POST'])
def switch_to_human(user_id):
    """Manually switch user to HUMAN mode"""
    chatbot.switch_to_human(user_id)
    return jsonify({
        "user_id": user_id,
        "mode": "human",
        "message": "User switched to HUMAN mode"
    }), 200


@app.route('/mode/<user_id>/ai', methods=['POST'])
def switch_to_ai(user_id):
    """Manually switch user back to AI mode"""
    chatbot.switch_to_ai(user_id)
    return jsonify({
        "user_id": user_id,
        "mode": "ai",
        "message": "User switched back to AI mode"
    }), 200


@app.route('/test', methods=['GET', 'POST'])
def test():
    """Test endpoint - GET for chat interface, POST same as /chat"""
    if request.method == 'GET':
        return send_from_directory(STATIC_FOLDER, 'chat.html')
    return chat()


def initialize():
    """Initialize chatbot"""
    global chatbot
    
    print("=" * 60)
    print("🤖 Simple Chatbot API - Your Roadmap")
    print("=" * 60)
    print("Step 1: Message → Groq API (Intent)")
    print("Step 2: Intent → Search API")
    print("Step 3: Results → Database Format")
    print("Step 4: Database → AI Formatting")
    print("Step 5: Track AI/HUMAN mode")
    print("Step 6: Return JSON with mode")
    print("=" * 60)
    
    try:
        chatbot = SimpleChatbot()
        print("✅ Chatbot initialized successfully!")
        print(f"🔗 BDStall API: {chatbot.api_url}")
        print(f"🤖 Groq API: {'Available' if chatbot.groq_client else 'Not available'}")
        print("=" * 60)
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        raise


if __name__ == '__main__':
    # Initialize
    initialize()
    
    # Get port
    port = int(os.getenv('PORT', 5000))
    
    print()
    print("🌐 Server starting...")
    print(f"📍 URL: http://localhost:{port}")
    print(f"📖 Docs: http://localhost:{port}/")
    print()
    print("⏸️  Press CTRL+C to stop")
    print()
    
    # Run
    app.run(host='0.0.0.0', port=port, debug=False)
