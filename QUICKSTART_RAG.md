# Quick Start Guide: Using RAG with Your Chatbot

This guide will help you quickly set up and use the RAG (Retrieval-Augmented Generation) feature.

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Verify RAG Installation

```bash
python test_rag.py
```

All tests should pass ✓

## Step 3: Add Your Documents

Place your knowledge base files in `data/knowledge/`:

```
data/knowledge/
├── company_info.txt      (company details)
├── products.txt          (product information)
├── policies.md           (policies and procedures)
├── faq.json              (frequently asked questions)
└── support_info.csv      (support documentation)
```

**Supported formats**: `.txt`, `.md`, `.json`, `.csv`

## Step 4: Test RAG

Run the example script:

```bash
python rag_example.py
```

This will:
- Load your documents
- Create vector embeddings
- Test semantic search
- Show example queries and responses

## Step 5: Use in Your Application

### Option A: Using with Flask App

The Flask app (`app.py`) automatically uses RAG. Just run:

```bash
python app.py
```

### Option B: Programmatic Usage

```python
from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data

# Initialize chatbot with RAG
chatbot = AdminChatbot(
    data_file="data/admin_data.json",
    csv_database="database.csv",
    enable_rag=True,
    rag_top_k=3  # Retrieve top 3 relevant documents
)

# Load knowledge base
initialize_rag_with_data(chatbot)

# Use the chatbot
response = chatbot.get_response(
    user_id="user123",
    message="What is your refund policy?"
)
print(response)
```

## Common Use Cases

### 1. Customer Support Bot

```python
from knowledge_loader import KnowledgeBaseLoader

loader = KnowledgeBaseLoader(chatbot.rag_store)

# Load support documentation
loader.load_from_text_files("data/support_docs")
loader.load_from_markdown("docs/troubleshooting.md")

# Now answers support questions from your docs
response = chatbot.get_response("user", "How do I reset my password?")
```

### 2. Product Information Bot

```python
# Load product catalog
loader.load_from_csv("data/products.csv", text_column="description")
loader.load_from_json("data/product_details.json")

# Answer product questions
response = chatbot.get_response("user", "Tell me about Product X")
```

### 3. Company Policy Bot

```python
# Load policies
loader.load_from_text_files("data/policies")
loader.load_from_markdown("employee_handbook.md")

# Answer policy questions
response = chatbot.get_response("user", "What is the vacation policy?")
```

## Adding More Documents Later

### Add Files to Knowledge Directory

Just add new files to `data/knowledge/` and reload:

```python
from knowledge_loader import initialize_rag_with_data

# This will load all new files
initialize_rag_with_data(chatbot)
```

### Add Documents Programmatically

```python
# Add text directly
documents = [
    "New product feature: Advanced analytics dashboard",
    "Updated policy: Remote work now allowed 3 days/week"
]

metadata = [
    {"source": "product_update", "date": "2026-01-24"},
    {"source": "policy_update", "date": "2026-01-24"}
]

chatbot.add_documents_to_rag(documents, metadata)
```

## Checking RAG Status

```python
# Get statistics
stats = chatbot.get_rag_stats()
print(stats)
# Output:
# {
#     'enabled': True,
#     'total_documents': 150,
#     'embedding_model': 'all-MiniLM-L6-v2',
#     'index_size': 150
# }
```

## Tuning RAG Performance

### Adjust Number of Retrieved Documents

```python
# Retrieve more context (better for complex questions)
chatbot = AdminChatbot(enable_rag=True, rag_top_k=5)

# Retrieve less context (faster, more focused)
chatbot = AdminChatbot(enable_rag=True, rag_top_k=2)
```

### Adjust Chunk Size

```python
# Smaller chunks (better for specific queries)
chatbot.rag_store.add_documents(
    documents=your_docs,
    chunk_size=300,
    overlap=50
)

# Larger chunks (better for broader context)
chatbot.rag_store.add_documents(
    documents=your_docs,
    chunk_size=800,
    overlap=100
)
```

## Troubleshooting

### Issue: "No relevant documents found"

**Solutions:**
- Add more documents to `data/knowledge/`
- Increase `rag_top_k` parameter
- Check that files were loaded: `chatbot.get_rag_stats()`

### Issue: Responses not accurate

**Solutions:**
- Ensure documents contain relevant information
- Increase `rag_top_k` from 3 to 5-7
- Make documents more detailed and specific

### Issue: Slow performance

**Solutions:**
- Reduce `rag_top_k` from 3 to 2
- Use smaller chunk sizes
- Reduce number of documents

### Issue: Import errors

**Solution:**
```bash
pip install sentence-transformers faiss-cpu numpy
```

## File Structure Reference

```
ai_chatbot/
├── data/
│   ├── knowledge/              ← Add your documents here
│   │   ├── *.txt              (text files)
│   │   ├── *.md               (markdown)
│   │   ├── *.json             (JSON)
│   │   └── *.csv              (CSV)
│   ├── admin_data.json        (admin context)
│   ├── rag_index.faiss        (auto-generated vector index)
│   └── rag_metadata.pkl       (auto-generated metadata)
├── rag_example.py             ← Run this to test
├── test_rag.py                ← Run this to verify installation
└── RAG_README.md              ← Detailed documentation
```

## Next Steps

1. ✅ Install dependencies
2. ✅ Run `test_rag.py` to verify
3. ✅ Add your documents to `data/knowledge/`
4. ✅ Run `rag_example.py` to test
5. ✅ Integrate into your app

## Getting Help

- See [RAG_README.md](RAG_README.md) for detailed documentation
- See [README.md](README.md) for general chatbot documentation
- Check example code in [rag_example.py](rag_example.py)

## Performance Tips

- **Start simple**: Begin with 10-20 documents
- **Quality over quantity**: Well-written documents > many poor documents
- **Keep updated**: Regularly refresh your knowledge base
- **Monitor logs**: Check `logs/` to see how RAG is performing
- **Test queries**: Try different questions to see retrieval quality

---

**That's it! Your chatbot now has RAG superpowers! 🚀**
