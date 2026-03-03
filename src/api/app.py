"""
BDStall Chatbot System Integration - Updated Flask App
Facebook Messenger Integration & Web Chat Interface with Full Architecture
"""
import os
import sys
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the new integrated system
try:
    from src.core.bdstall_chatbot_system import BDStallChatbotSystem, ChatbotIntegration
except ImportError:
    from core.bdstall_chatbot_system import BDStallChatbotSystem, ChatbotIntegration

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Initialize new integrated chatbot system
chatbot_system = None
chatbot_integration = None

# Facebook Page Access Token and Verify Token
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'my_verify_token_12345')


def send_message(recipient_id: str, message_text: str) -> bool:
    """
    Send a message to a Facebook Messenger user
    
    Args:
        recipient_id: Facebook user ID
        message_text: Message to send
        
    Returns:
        True if successful, False otherwise
    """
    if not PAGE_ACCESS_TOKEN:
        logger.error("PAGE_ACCESS_TOKEN not set")
        return False
    
    try:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            logger.info(f"Message sent successfully to {recipient_id}")
            return True
        else:
            logger.error(f"Failed to send message: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Verify webhook for Facebook Messenger
    Facebook will send a GET request to verify the webhook
    """
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return challenge, 200
        else:
            logger.warning("Webhook verification failed")
            return 'Forbidden', 403
    
    return 'Bad Request', 400


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages from Facebook Messenger using new system"""
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {data}")
        
        # Process messaging events
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    
                    sender_id = messaging_event['sender']['id']
                    
                    # Handle text messages
                    if messaging_event.get('message'):
                        message = messaging_event['message']
                        
                        if message.get('text'):
                            message_text = message['text']
                            logger.info(f"Received message from {sender_id}: {message_text}")
                            
                            # Use new integrated system for processing
                            result = chatbot_system.process_message(
                                user_id=sender_id,
                                message=message_text,
                                channel="facebook",
                                metadata={
                                    "message_id": message.get("mid"),
                                    "timestamp": messaging_event.get("timestamp")
                                }
                            )
                            
                            if result.get("handover"):
                                logger.info(f"Handover active for {sender_id}; skipping AI reply")
                            else:
                                response_text = result.get("response", "দুঃখিত, কিছু সমস্যা হয়েছে।")
                                send_message(sender_id, response_text)
                    
                    # Handle postbacks (button clicks)
                    elif messaging_event.get('postback'):
                        payload = messaging_event['postback']['payload']
                        logger.info(f"Received postback from {sender_id}: {payload}")
                        
                        # Process postback using new system
                        result = chatbot_system.process_message(
                            user_id=sender_id,
                            message=payload,
                            channel="facebook",
                            metadata={
                                "type": "postback",
                                "title": messaging_event['postback'].get('title')
                            }
                        )
                        
                        if result.get("handover"):
                            logger.info(f"Handover active for {sender_id}; skipping AI reply")
                        else:
                            response_text = result.get("response", "ধন্যবাদ!")
                            send_message(sender_id, response_text)
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return 'Internal Server Error', 500


@app.route('/', methods=['GET'])
def index():
    """Serve the chat HTML interface"""
    try:
        # Try to serve from static folder (new structure)
        static_path = os.path.join(os.path.dirname(__file__), '..', '..', 'static')
        return send_from_directory(static_path, 'chat.html')
    except:
        # Fallback if chat.html not found
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>AI Chatbot</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
        .chat-container { width: 90%; max-width: 600px; height: 80vh; background: white; border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.3); display: flex; flex-direction: column; overflow: hidden; }
        .chat-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }
        .chat-header h1 { font-size: 24px; }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; background: #f5f5f5; }
        .message { margin: 10px 0; display: flex; }
        .message.user { justify-content: flex-end; }
        .message.bot { justify-content: flex-start; }
        .message-content { max-width: 70%; padding: 12px 16px; border-radius: 18px; word-wrap: break-word; white-space: pre-wrap; }
        .message.user .message-content { background: #667eea; color: white; }
        .message.bot .message-content { background: white; color: #333; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .chat-input { display: flex; padding: 20px; background: white; border-top: 1px solid #e0e0e0; }
        .chat-input input { flex: 1; padding: 12px; border: 2px solid #e0e0e0; border-radius: 25px; font-size: 16px; outline: none; }
        .chat-input input:focus { border-color: #667eea; }
        .chat-input button { margin-left: 10px; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 16px; font-weight: bold; }
        .chat-input button:hover { opacity: 0.9; }
        .typing { opacity: 0.6; font-style: italic; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🤖 AI Chatbot</h1>
            <p>Ask about products, prices, or anything!</p>
        </div>
        <div class="chat-messages" id="chatMessages"></div>
        <div class="chat-input">
            <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="if(event.key===\'Enter\')sendMessage()">
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>
    <script>
        function addMessage(text, isUser) {
            const messagesDiv = document.getElementById(\'chatMessages\');
            const messageDiv = document.createElement(\'div\');
            messageDiv.className = \'message \' + (isUser ? \'user\' : \'bot\');
            const contentDiv = document.createElement(\'div\');
            contentDiv.className = \'message-content\';
            contentDiv.textContent = text;
            messageDiv.appendChild(contentDiv);
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        async function sendMessage() {
            const input = document.getElementById(\'messageInput\');
            const message = input.value.trim();
            if (!message) return;
            addMessage(message, true);
            input.value = \'\';
            addMessage(\'Typing...\', false);
            try {
                const response = await fetch(\'/chat\', {
                    method: \'POST\',
                    headers: { \'Content-Type\': \'application/json\' },
                    body: JSON.stringify({ user_id: \'web_user\', message: message })
                });
                const data = await response.json();
                const messages = document.getElementsByClassName(\'message\');
                messages[messages.length - 1].remove();
                addMessage(data.response, false);
            } catch (error) {
                const messages = document.getElementsByClassName(\'message\');
                messages[messages.length - 1].remove();
                addMessage(\'Error: Could not get response. Please try again.\', false);
            }
        }
        addMessage(\'আসসালামু আলাইকুম! I\\'m your AI assistant. Ask me about products, prices, or anything!\', false);
    </script>
</body>
</html>
        ''', 200


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from web interface using new system"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'web_user')
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        # Use new integrated system
        result = chatbot_system.process_message(
            user_id=user_id,
            message=message,
            channel="web",
            metadata={
                "ip_address": request.remote_addr,
                "user_agent": request.headers.get('User-Agent')
            }
        )
        
        if result.get("handover"):
            return jsonify({
                "response": "",
                "handover": True,
                "user_id": user_id,
                "processing_info": result.get("processing_info", {}),
                "success": True
            }), 200

        if result["success"]:
            return jsonify({
                "response": result["response"],
                "user_id": user_id,
                "processing_info": result.get("processing_info", {}),
                "success": True
            }), 200
        else:
            return jsonify({
                "response": result["response"],
                "error": result.get("error", "Unknown error"),
                "success": False
            }), 500
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Failed to process message",
            "response": "দুঃখিত, আমি এই মুহূর্তে আপনার বার্তা প্রসেস করতে পারছি না।",
            "success": False
        }), 500


@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Clear conversation history for a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'web_user')
        
        # Use new system's clear method
        chatbot_system.clear_user_data(user_id)
        
        return jsonify({"status": "success", "message": "History cleared"}), 200
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats', methods=['GET'])
def stats():
    """Get chatbot statistics (legacy endpoint for compatibility)"""
    try:
        health = chatbot_system.get_system_health()
        return jsonify({
            "chatbot_loaded": chatbot_system is not None,
            "system_health": health
        }), 200
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        health = chatbot_system.get_system_health()
        return jsonify({
            "status": health["status"],
            "chatbot_loaded": chatbot_system is not None,
            "components": health["components"]
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@app.route('/test', methods=['POST'])
def test_message():
    """Test endpoint using new system"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'test_user')
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        # Use new system for testing
        result = chatbot_system.process_message(
            user_id=user_id,
            message=message,
            channel="api",
            metadata={"test_mode": True}
        )
        
        return jsonify({
            "user_id": user_id,
            "message": message,
            "response": result["response"],
            "success": result["success"],
            "processing_info": result.get("processing_info", {}),
            "system_info": "BDStall Chatbot System v1.0"
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500


# New endpoints for enhanced functionality
@app.route('/conversation_history/<user_id>', methods=['GET'])
def get_conversation_history(user_id):
    """Get conversation history for a user (new endpoint)"""
    try:
        history = chatbot_system.get_user_conversation_history(user_id)
        return jsonify(history), 200
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/system_health', methods=['GET'])
def system_health():
    """Get comprehensive system health (new endpoint)"""
    try:
        health = chatbot_system.get_system_health()
        return jsonify(health), 200
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/analytics', methods=['GET'])
def get_analytics():
    """Get system analytics (new endpoint)"""
    try:
        # Get analytics from the system
        analytics = chatbot_system._get_analytics_data()
        return jsonify({
            "status": "success",
            "analytics": analytics,
            "timestamp": chatbot_system.get_system_health()["timestamp"]
        }), 200
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/process', methods=['POST'])
def process_message_detailed():
    """Process message with detailed response information"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'api_user')
        message = data.get('message', '')
        channel = data.get('channel', 'api')
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        # Process with full details
        result = chatbot_system.process_message(
            user_id=user_id,
            message=message,
            channel=channel,
            metadata=data.get('metadata', {})
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error in detailed processing: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "response": "System error occurred"
        }), 500


def initialize_chatbot():
    """Initialize the new BDStall chatbot system"""
    global chatbot_system, chatbot_integration
    
    logger.info("Initializing BDStall Chatbot System...")
    
    try:
        # Initialize the main system
        chatbot_system = BDStallChatbotSystem(
            enable_rag=True,
            enable_multimedia=True,
            enable_analytics=True
        )
        
        # Initialize compatibility layer
        chatbot_integration = ChatbotIntegration()
        
        logger.info("🚀 BDStall Chatbot System ready!")
        
        # Show system health
        health = chatbot_system.get_system_health()
        logger.info(f"System Status: {health['status']}")
        logger.info("Components:")
        for component, status in health['components'].items():
            logger.info(f"  ✓ {component}: {status}")
        
    except Exception as e:
        logger.error(f"Failed to initialize chatbot system: {e}")
        raise


if __name__ == '__main__':
    # Initialize new chatbot system
    initialize_chatbot()
    
    # Show startup information
    print("=" * 60)
    print("🤖 BDStall AI Chatbot Server")
    print("=" * 60)
    print("New Architectural Components:")
    print("✓ Channel Adapter - Multi-channel support")
    print("✓ Intent & Entity Detection - NLP processing")  
    print("✓ Context Router - Conversation management")
    print("✓ Business Rule Engine - Logic processing")
    print("✓ Decision Router - Strategy selection")
    print("✓ Response Composer - Final response generation")
    print("=" * 60)
    print("Available Endpoints:")
    print("• POST /test - Test the system")
    print("• POST /process - Detailed message processing")
    print("• GET /system_health - System health status") 
    print("• GET /analytics - System analytics")
    print("• GET /conversation_history/<user_id> - User history")
    print("=" * 60)
    
    # Run Flask app
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
