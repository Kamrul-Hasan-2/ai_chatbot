"""
Facebook Messenger Integration & Web Chat Interface
Flask webhook for receiving and responding to messages
Enhanced with RAG support and product search
"""
import os
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Initialize chatbot (will be done after app starts)
chatbot = None

# Facebook Page Access Token and Verify Token
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'my_verify_token_12345')

# RAG Configuration
ENABLE_RAG = os.getenv('ENABLE_RAG', 'true').lower() == 'true'
RAG_TOP_K = int(os.getenv('RAG_TOP_K', '3'))


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
    """
    Handle incoming messages from Facebook Messenger
    """
    try:
        data = request.get_json()
        
        # Log incoming data
        logger.info(f"Received webhook data: {data}")
        
        # Process messaging events
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    
                    sender_id = messaging_event['sender']['id']
                    
                    # Handle text messages
                    if messaging_event.get('message'):
                        message = messaging_event['message']
                        
                        # Check if it's a text message
                        if message.get('text'):
                            message_text = message['text']
                            logger.info(f"Received message from {sender_id}: {message_text}")
                            
                            # Get AI response
                            response = chatbot.get_response(sender_id, message_text)
                            
                            # Send response back
                            send_message(sender_id, response)
                    
                    # Handle postbacks (button clicks)
                    elif messaging_event.get('postback'):
                        payload = messaging_event['postback']['payload']
                        logger.info(f"Received postback from {sender_id}: {payload}")
                        
                        # Handle postback as a message
                        response = chatbot.get_response(sender_id, payload)
                        send_message(sender_id, response)
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return 'Internal Server Error', 500


@app.route('/', methods=['GET'])
def index():
    """Serve the chat HTML interface"""
    try:
        return send_from_directory('.', 'chat.html')
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
    """Handle chat messages from web interface"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'web_user')
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        # Get chatbot response
        response = chatbot.get_response(user_id, message)
        
        return jsonify({
            "response": response,
            "user_id": user_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Failed to process message",
            "response": "দুঃখিত, আমি এই মুহূর্তে আপনার বার্তা প্রসেস করতে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।"
        }), 500


@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Clear conversation history for a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'web_user')
        chatbot.clear_history(user_id)
        return jsonify({"status": "success", "message": "History cleared"}), 200
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats', methods=['GET'])
def stats():
    """Get chatbot statistics"""
    try:
        rag_stats = chatbot.get_rag_stats() if chatbot else {}
        return jsonify({
            "chatbot_loaded": chatbot is not None,
            "rag_stats": rag_stats
        }), 200
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "chatbot_loaded": chatbot is not None
    }), 200


@app.route('/test', methods=['POST'])
def test_message():
    """
    Test endpoint to send a message without Messenger
    POST with JSON: {"user_id": "test_user", "message": "Hello"}
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'test_user')
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        response = chatbot.get_response(user_id, message)
        
        return jsonify({
            "user_id": user_id,
            "message": message,
            "response": response
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        return jsonify({"error": str(e)}), 500


def initialize_chatbot():
    """Initialize the chatbot with RAG support (called when app starts)"""
    global chatbot
    logger.info("Initializing chatbot...")
    logger.info(f"RAG enabled: {ENABLE_RAG}")
    
    # Initialize chatbot with RAG
    chatbot = AdminChatbot(
        enable_rag=ENABLE_RAG,
        rag_top_k=RAG_TOP_K
    )
    
    # Load knowledge base if RAG is enabled
    if ENABLE_RAG:
        logger.info("Loading knowledge base into RAG store...")
        try:
            results = initialize_rag_with_data(
                chatbot, 
                knowledge_dirs=["data/knowledge", "docs"]
            )
            logger.info(f"RAG initialized: {results}")
            
            # Show RAG stats
            stats = chatbot.get_rag_stats()
            logger.info(f"RAG Stats: {stats}")
        except Exception as e:
            logger.warning(f"RAG initialization warning: {e}")
            logger.info("Continuing without RAG enhancement")
    
    logger.info("Chatbot ready!")


if __name__ == '__main__':
    # Initialize chatbot
    initialize_chatbot()
    
    # Run Flask app
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
