# RAG (Retrieval-Augmented Generation) System

## Overview

This chatbot now includes RAG functionality for better, more accurate responses. RAG enhances the AI by retrieving relevant information from your knowledge base before generating responses.

## How RAG Works

1. **Document Storage**: Your documents are split into chunks and converted to vector embeddings
2. **Semantic Search**: When a user asks a question, the system finds the most relevant document chunks
3. **Enhanced Generation**: The AI uses the retrieved information to generate accurate, contextual responses

## Architecture

```
User Query
    ↓
[CSV Database Check] → Direct Answer (if exact match)
    ↓ (if no match)
[RAG Retrieval] → Find relevant documents
    ↓
[AI Model] → Generate response using retrieved context
    ↓
Response to User
```

## Installation

Install the additional dependencies:

```bash
pip install sentence-transformers faiss-cpu numpy
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data

# Initialize chatbot with RAG enabled
chatbot = AdminChatbot(
    data_file="data/admin_data.json",
    csv_database="database.csv",
    enable_rag=True,      # Enable RAG
    rag_top_k=3           # Retrieve top 3 documents
)

# Load your knowledge base
initialize_rag_with_data(chatbot, knowledge_dirs=["data/knowledge", "docs"])

# Use the chatbot
response = chatbot.get_response(user_id="user_123", message="What is your refund policy?")
```

### Adding Documents

#### Method 1: Direct API

```python
# Add documents directly
documents = [
    "Our company offers 24/7 support",
    "We have a 30-day money-back guarantee",
    "Shipping is free over $50"
]

metadata = [
    {"source": "support", "type": "policy"},
    {"source": "refund", "type": "policy"},
    {"source": "shipping", "type": "policy"}
]

chatbot.add_documents_to_rag(documents, metadata)
```

#### Method 2: Using Knowledge Loader

```python
from knowledge_loader import KnowledgeBaseLoader

loader = KnowledgeBaseLoader(chatbot.rag_store)

# Load from text files
loader.load_from_text_files("data/knowledge")

# Load from JSON
loader.load_from_json("data/faq.json", text_field="content")

# Load from CSV
loader.load_from_csv("data/products.csv", text_column="description")

# Load from Markdown
loader.load_from_markdown("docs/README.md")

# Load everything at once
results = loader.load_knowledge_base(
    text_dirs=["data/knowledge", "docs"],
    json_files=["data/faq.json"],
    csv_files=["data/products.csv"],
    markdown_files=["README.md"],
    include_admin_data=True
)
```

## Configuration

### RAG Parameters

```python
chatbot = AdminChatbot(
    enable_rag=True,      # Enable/disable RAG
    rag_top_k=3           # Number of documents to retrieve (1-10 recommended)
)
```

### Document Chunking

Documents are automatically split into chunks:
- **Default chunk size**: 500 characters
- **Overlap**: 50 characters
- Chunks at sentence boundaries when possible

You can customize this:

```python
chatbot.rag_store.add_documents(
    documents=your_docs,
    chunk_size=1000,  # Larger chunks
    overlap=100       # More overlap
)
```

## File Structure

```
ai_chatbot/
├── rag_store.py              # Core RAG implementation
├── knowledge_loader.py        # Utilities to load documents
├── chatbot.py                # Enhanced with RAG integration
├── ai_model.py               # Enhanced prompt for RAG
├── rag_example.py            # Usage examples
├── data/
│   ├── admin_data.json       # Admin context (auto-loaded)
│   ├── knowledge/            # Put knowledge base files here
│   │   ├── product_info.txt
│   │   ├── policies.md
│   │   └── faq.json
│   ├── rag_index.faiss       # Vector index (auto-generated)
│   └── rag_metadata.pkl      # Document metadata (auto-generated)
```

## Supported File Formats

- **Text files** (`.txt`)
- **JSON** (`.json`)
- **CSV** (`.csv`)
- **Markdown** (`.md`)

## Features

### 1. Semantic Search
Uses sentence-transformers for semantic similarity, not just keyword matching.

### 2. Automatic Chunking
Long documents are automatically split into manageable chunks with overlap.

### 3. Persistent Storage
Vector index and metadata are saved to disk and reloaded automatically.

### 4. Multi-Source Loading
Load documents from multiple file formats and directories.

### 5. Metadata Support
Attach metadata to documents for better tracking and filtering.

## Performance Tips

1. **Chunk Size**: Smaller chunks (300-500 chars) work better for specific queries. Larger chunks (800-1200 chars) work better for broader context.

2. **Top K**: Start with 3-5 documents. Increase if responses lack detail, decrease if responses are too verbose.

3. **Document Quality**: Clean, well-structured documents produce better results.

4. **Update Regularly**: Refresh your knowledge base as information changes.

## Example Scenarios

### Customer Support Bot

```python
# Load support documentation
loader.load_from_text_files("data/support_docs")
loader.load_from_json("data/common_issues.json")

# Now chatbot can answer from documentation
response = chatbot.get_response("user123", "How do I reset my password?")
```

### Product Information Bot

```python
# Load product catalog
loader.load_from_csv("data/products.csv", text_column="description")
loader.load_from_markdown("data/product_features.md")

# Answer product questions
response = chatbot.get_response("user456", "What are the features of product X?")
```

### Company Policy Bot

```python
# Load company policies
loader.load_from_text_files("data/policies")
loader.load_from_markdown("employee_handbook.md")

# Answer policy questions
response = chatbot.get_response("employee789", "What is the vacation policy?")
```

## Monitoring

Check RAG statistics:

```python
stats = chatbot.get_rag_stats()
print(stats)
# Output:
# {
#     'enabled': True,
#     'total_documents': 150,
#     'embedding_model': 'all-MiniLM-L6-v2',
#     'embedding_dimension': 384,
#     'index_size': 150
# }
```

## Troubleshooting

### Issue: "No relevant documents found"
- **Solution**: Check if documents are loaded: `chatbot.get_rag_stats()`
- Add more documents or adjust chunk size

### Issue: "Responses not using RAG context"
- **Solution**: Increase `rag_top_k` parameter
- Ensure documents contain relevant information

### Issue: "Slow performance"
- **Solution**: Reduce `rag_top_k`
- Use GPU if available (FAISS will auto-detect)

### Issue: "Import errors"
- **Solution**: Install dependencies: `pip install sentence-transformers faiss-cpu numpy`

## Advanced Usage

### Custom Embedding Model

```python
from rag_store import RAGStore

# Use a different embedding model
rag_store = RAGStore(model_name="all-mpnet-base-v2")
```

### Search Directly

```python
# Search the RAG store directly
results = chatbot.rag_store.search(
    query="refund policy",
    top_k=5,
    score_threshold=0.7  # Only return results with similarity > 0.7
)

for doc, score, metadata in results:
    print(f"Score: {score:.2f}")
    print(f"Source: {metadata.get('source')}")
    print(f"Content: {doc[:100]}...")
```

### Clear and Rebuild Index

```python
# Clear existing index
chatbot.rag_store.clear_index()

# Reload all documents
initialize_rag_with_data(chatbot)
```

## Benefits of RAG

1. **Accuracy**: Responses based on your actual documents and data
2. **Up-to-date**: Easy to update knowledge base without retraining
3. **Transparency**: Can track which documents were used for responses
4. **Scalability**: Handle large knowledge bases efficiently
5. **Flexibility**: Support multiple document formats and sources

## Next Steps

1. Create a `data/knowledge` directory
2. Add your documentation files (txt, json, csv, md)
3. Run `python rag_example.py` to see it in action
4. Integrate with your application

## API Reference

See the code documentation in:
- `rag_store.py` - Core RAG functionality
- `knowledge_loader.py` - Document loading utilities
- `chatbot.py` - Enhanced chatbot with RAG integration
