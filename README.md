# AI Chatbot with Qwen2-VL-2B-Instruct + RAG

An intelligent chatbot system that uses the Qwen2-VL-2B-Instruct model with RAG (Retrieval-Augmented Generation) to respond to Facebook Messenger messages as an admin. The bot can understand your business data and provide accurate, context-aware responses enhanced with semantic search.

## Features

- 🤖 **AI-Powered Responses**: Uses Qwen2-VL-2B-Instruct for intelligent conversation
- 🔍 **RAG Enhancement**: Retrieval-Augmented Generation for better accuracy
- 💼 **Admin Context**: Loads your business data to respond accurately
- 💬 **Facebook Messenger Integration**: Seamlessly integrates with Facebook Messenger
- 📝 **Conversation History**: Maintains context across multiple messages
- 📊 **Logging**: Tracks all conversations for review
- 📚 **Knowledge Base**: Load documents from multiple formats (txt, json, csv, md)
- 🎯 **Semantic Search**: Find relevant information using vector embeddings
- 🧪 **Test Endpoint**: Test the bot without Messenger integration

## What's New: RAG System

The chatbot now includes RAG (Retrieval-Augmented Generation) which significantly improves response quality by:
- Retrieving relevant information from your knowledge base before responding
- Using semantic search (not just keywords) to find the best matches
- Combining retrieved context with AI generation for accurate answers
- Supporting multiple document formats and sources

**See [RAG_README.md](RAG_README.md) for detailed RAG documentation.**

## Project Structure

```
ai_chatbot/
├── app.py                      # Flask application with Messenger webhook
├── chatbot.py                  # Main chatbot logic (RAG-enhanced)
├── ai_model.py                 # Qwen AI model handler
├── rag_store.py                # RAG vector store and search
├── knowledge_loader.py         # Utilities to load documents
├── database_handler.py         # CSV database handler
├── rag_example.py              # RAG usage examples
├── test_rag.py                 # RAG verification test
├── requirements.txt            # Python dependencies (updated with RAG)
├── RAG_README.md               # Detailed RAG documentation
├── .env.example               # Environment variables template
├── .env                       # Your actual environment variables (create this)
├── data/
│   ├── admin_data.json        # Your business data (customize this!)
│   ├── knowledge/             # Put your knowledge base files here (NEW)
│   │   ├── company_info.txt
│   │   ├── products.txt
│   │   ├── support_policies.txt
│   │   └── faq.md
│   ├── rag_index.faiss        # Vector index (auto-generated)
│   └── rag_metadata.pkl       # Document metadata (auto-generated)
├── logs/                      # Conversation logs (auto-created)
└── database.csv               # Q&A database
```

## Setup Instructions

### 1. Install Dependencies

First, make sure you have Python 3.8+ installed. Then install the required packages:

```bash
pip install -r requirements.txt
```

This now includes:
- `sentence-transformers` for embeddings
- `faiss-cpu` for vector search
- `numpy` for numerical operations

**Note**: The first time you run the bot, it will download:
- The Qwen2-VL-2B-Instruct model (~5GB)
- The sentence-transformers embedding model (~90MB)
This may take some time depending on your internet connection.

### 2. Verify RAG Installation

Test that RAG is working correctly:

```bash
python test_rag.py
```

You should see all tests passing ✓

### 3. Configure Your Data

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

### 5. Load Your Knowledge Base (RAG)

Add your documents to the knowledge base:

1. **Add files to `data/knowledge/` directory**:
   - Text files (`.txt`)
   - Markdown files (`.md`)
   - JSON files (`.json`)
   - CSV files (`.csv`)

2. **Run the RAG example to load documents**:
   ```bash
   python rag_example.py
   ```

3. **Or load programmatically in your code**:
   ```python
   from knowledge_loader import initialize_rag_with_data
   initialize_rag_with_data(chatbot, knowledge_dirs=["data/knowledge"])
   ```

Sample knowledge files are already included in `data/knowledge/` for demonstration.

## Usage

### Running the Bot (with RAG)

```bash
python app.py
```

The chatbot will:
1. Load the AI model
2. Initialize RAG store
3. Load documents from `data/knowledge/`
4. Start the Flask server on `http://localhost:5000`

### Testing RAG

Test the RAG-enhanced bot:

```bash
python rag_example.py
```

This demonstrates:
- Loading documents into RAG
- Semantic search
- Enhanced responses using retrieved context

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
2. **Load more documents into RAG** - Add relevant files to `data/knowledge/`
3. Review conversation logs in `logs/` folder
4. Adjust `rag_top_k` parameter (default: 3, try 5-7 for more context)
5. Adjust temperature (lower = more focused, higher = more creative)

## RAG (Retrieval-Augmented Generation)

### What is RAG?

RAG enhances the chatbot by:
1. **Retrieving** relevant information from your knowledge base
2. **Augmenting** the AI's context with this information
3. **Generating** more accurate, informed responses

### Quick Start with RAG

```python
from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data

# Initialize with RAG enabled
chatbot = AdminChatbot(enable_rag=True, rag_top_k=3)

# Load knowledge base
initialize_rag_with_data(chatbot)

# Use normally
response = chatbot.get_response("user123", "What is your refund policy?")
```

### RAG Configuration

```python
chatbot = AdminChatbot(
    enable_rag=True,      # Enable/disable RAG
    rag_top_k=3           # Number of documents to retrieve
)
```

### Adding Documents to RAG

```python
# Direct method
chatbot.add_documents_to_rag(
    documents=["Your document text"],
    metadata=[{"source": "manual"}]
)

# Using loader
from knowledge_loader import KnowledgeBaseLoader
loader = KnowledgeBaseLoader(chatbot.rag_store)
loader.load_from_text_files("data/knowledge")
loader.load_from_json("data/my_data.json")
```

**For complete RAG documentation, see [RAG_README.md](RAG_README.md)**

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
