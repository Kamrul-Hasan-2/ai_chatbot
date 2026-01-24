"""
Facebook Messenger Integration
Flask webhook for receiving and responding to messages
"""
import os
import logging
from flask import Flask, request, jsonify
import requests
from chatbot import AdminChatbot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize chatbot (will be done after app starts)
chatbot = None

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
    """Initialize the chatbot (called when app starts)"""
    global chatbot
    logger.info("Initializing chatbot...")
    chatbot = AdminChatbot()
    logger.info("Chatbot ready!")


if __name__ == '__main__':
    # Initialize chatbot
    initialize_chatbot()
    
    # Run Flask app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
