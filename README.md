# AI Chatbot with Qwen2-VL-2B-Instruct

An intelligent chatbot system that uses the Qwen2-VL-2B-Instruct model to respond to Facebook Messenger messages as an admin. The bot can understand your business data and provide accurate, context-aware responses.

## Features

- 🤖 **AI-Powered Responses**: Uses Qwen2-VL-2B-Instruct for intelligent conversation
- 💼 **Admin Context**: Loads your business data to respond accurately
- 💬 **Facebook Messenger Integration**: Seamlessly integrates with Facebook Messenger
- 📝 **Conversation History**: Maintains context across multiple messages
- 📊 **Logging**: Tracks all conversations for review
- 🧪 **Test Endpoint**: Test the bot without Messenger integration

## Project Structure

```
ai_chatbot/
├── app.py                  # Flask application with Messenger webhook
├── chatbot.py             # Main chatbot logic
├── ai_model.py            # Qwen AI model handler
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .env                  # Your actual environment variables (create this)
├── data/
│   └── admin_data.json   # Your business data (customize this!)
└── logs/                 # Conversation logs (auto-created)
```

## Setup Instructions

### 1. Install Dependencies

First, make sure you have Python 3.8+ installed. Then install the required packages:

```bash
pip install -r requirements.txt
```

**Note**: The first time you run the bot, it will download the Qwen2-VL-2B-Instruct model (~5GB). This may take some time depending on your internet connection.

### 2. Configure Your Data

Edit `data/admin_data.json` with your business information:

```json
{
  "company_info": "Your company description",
  "products": ["Product 1", "Product 2"],
  "faq": [
    {
      "question": "Your question?",
      "answer": "Your answer"
    }
  ],
  "contact": {
    "email": "your@email.com",
    "phone": "+1-234-567-8900"
  }
}
```

The AI will use this data to answer customer questions accurately.

### 3. Set Up Environment Variables

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Edit `.env` and add your Facebook Page Access Token:

```
PAGE_ACCESS_TOKEN=your_facebook_page_access_token_here
VERIFY_TOKEN=my_verify_token_12345
PORT=5000
```

### 4. Set Up Facebook Messenger (Optional)

If you want to connect to Facebook Messenger:

1. **Create a Facebook App**:
   - Go to https://developers.facebook.com/
   - Create a new app
   - Add "Messenger" product

2. **Get Your Page Access Token**:
   - Go to Messenger settings
   - Generate a Page Access Token
   - Add it to your `.env` file

3. **Set Up Webhook**:
   - You need a public URL (use ngrok for testing: https://ngrok.com/)
   - Set webhook URL to: `https://your-domain.com/webhook`
   - Use the VERIFY_TOKEN from your `.env` file
   - Subscribe to `messages` and `messaging_postbacks` events

## Usage

### Running the Bot

```bash
python app.py
```

The server will start on `http://localhost:5000`

### Testing Without Messenger

You can test the bot using the `/test` endpoint:

```bash
curl -X POST http://localhost:5000/test ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\": \"test_user\", \"message\": \"Hello, what are your business hours?\"}"
```

Or using PowerShell:

```powershell
$body = @{
    user_id = "test_user"
    message = "Hello, what are your business hours?"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:5000/test -Method POST -Body $body -ContentType "application/json"
```

### Using with Messenger

Once set up, users can message your Facebook Page and the bot will automatically respond using your business data.

## Configuration Options

### Model Settings

You can adjust the AI model's behavior in `ai_model.py`:

- `max_length`: Maximum response length (default: 512)
- `temperature`: Creativity (0.1-1.0, higher = more creative, default: 0.7)
- `top_p`: Nucleus sampling (default: 0.9)

### Conversation History

The bot maintains the last 10 message exchanges per user. You can adjust this in `chatbot.py`:

```python
# Keep only last 10 exchanges (20 messages)
if len(self.conversation_history[user_id]) > 20:
    self.conversation_history[user_id] = self.conversation_history[user_id][-20:]
```

## System Requirements

- **RAM**: 4GB minimum, 8GB+ recommended
- **GPU**: Optional but recommended (CUDA-compatible)
- **Storage**: ~10GB for model and dependencies
- **Python**: 3.8 or higher

## Troubleshooting

### Model Loading Issues

If you encounter memory errors, try:
1. Close other applications
2. Use CPU instead of GPU by setting `DEVICE=cpu` in `.env`
3. Restart your computer

### Facebook Webhook Issues

- Make sure your webhook URL is publicly accessible
- Verify that VERIFY_TOKEN matches in both `.env` and Facebook settings
- Check that PAGE_ACCESS_TOKEN is correct

### Response Quality

If responses aren't accurate:
1. Check `data/admin_data.json` - make sure your data is detailed
2. Review conversation logs in `logs/` folder
3. Adjust temperature (lower = more focused, higher = more creative)

## Logs

All conversations are logged in the `logs/` directory:
- Filename format: `conversations_YYYY-MM-DD.log`
- Includes timestamps, user IDs, messages, and responses

## Security Notes

- Never commit `.env` file to version control
- Keep your PAGE_ACCESS_TOKEN secret
- Use HTTPS in production
- Regularly rotate access tokens

## Customization

### Adding New Features

You can extend the chatbot by:
1. Modifying the system prompt in `ai_model.py`
2. Adding new data fields in `admin_data.json`
3. Implementing custom message handlers in `app.py`

### Different Platforms

To use with other platforms (Telegram, Discord, etc.):
1. Keep `chatbot.py` and `ai_model.py` as-is
2. Replace `app.py` with platform-specific webhook handler
3. Call `chatbot.get_response()` with user messages

## License

MIT License - feel free to use and modify for your projects.

## Support

For issues or questions:
- Check the logs in `logs/` directory
- Review error messages in the console
- Ensure all dependencies are installed correctly

---

**Ready to use!** Edit your data file and start the bot. It will learn from your business information and respond intelligently to customer messages.
