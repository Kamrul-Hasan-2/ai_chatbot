# Project Structure

This document describes the organized file structure of the AI Chatbot project.

## Directory Organization

```
ai_chatbot/
├── .env                     # Environment variables (DO NOT COMMIT)
├── .env.example             # Example environment configuration
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container configuration
├── docker-compose.yml      # Docker compose setup
├── PROJECT_STRUCTURE.md    # This file
│
├── src/                    # Source Code
│   ├── api/               # API and application files
│   │   ├── app.py
│   │   └── app_integrated.py
│   │
│   ├── core/              # Core chatbot components
│   │   ├── chatbot.py
│   │   ├── bdstall_chatbot_system.py
│   │   ├── business_rule_engine.py
│   │   ├── context_router.py
│   │   ├── decision_router.py
│   │   ├── response_composer.py
│   │   ├── intent_entity_detector.py
│   │   └── mode_manager.py
│   │
│   ├── models/            # AI model implementations
│   │   ├── ai_model.py
│   │   ├── enhanced_ai_model.py
│   │   ├── robust_ai_model.py
│   │   ├── groq_model.py
│   │   └── gemini_model.py
│   │
│   ├── handlers/          # Various handler components
│   │   ├── database_handler.py
│   │   ├── bengali_database_handler.py
│   │   ├── fallback_handler.py
│   │   └── human_handoff_manager.py
│   │
│   └── utils/             # Utility functions and helpers
│       ├── product_search.py
│       ├── enhanced_product_search.py
│       ├── groq_3step_search.py
│       ├── simple_intent_search.py
│       ├── knowledge_loader.py
│       ├── rag_store.py
│       ├── rag_example.py
│       ├── channel_adapter.py
│       ├── messenger_api_loader.py
│       ├── fetch_training_data.py
│       └── get_new_token.py
│
├── tests/                 # Test files and demos
│   ├── test_*.py         # All test files
│   ├── demo_*.py         # Demo scripts
│   ├── chat_demo.py
│   ├── debug_hp_laptop.py
│   ├── setup_and_train.py
│   ├── train_ai.py
│   └── train_messenger.py
│
├── config/               # Configuration files
│   ├── nginx.conf
│   ├── nginx_no_ssl.conf
│   ├── gunicorn_config.py
│   └── chatbot.service
│
├── scripts/              # Utility and deployment scripts
│   ├── deployment/       # Deployment scripts
│   │   ├── deploy.sh
│   │   ├── deploy_vastai.sh
│   │   ├── setup_ssl.sh
│   │   ├── monitor.sh
│   │   ├── restart.sh
│   │   ├── start.sh
│   │   └── stop.sh
│   │
│   ├── health/           # Health check scripts
│   │   ├── health_check.sh
│   │   ├── health_check.ps1
│   │   └── check_status.sh
│   │
│   ├── RUN_PROJECT.bat   # Windows run script
│   ├── START_FACEBOOK_BOT.bat
│   ├── RUN_FACEBOOK_BOT.ps1
│   ├── MANAGE_MODES.bat
│   └── start.ps1
│
├── docs/                 # Documentation
│   ├── README.md
│   ├── QUICKSTART.md
│   ├── HOW_TO_RUN.md
│   ├── DEPLOYMENT.md
│   ├── FACEBOOK_SETUP_GUIDE.md
│   ├── GROQ_3STEP_IMPLEMENTATION.md
│   ├── HUMAN_HANDOFF_SYSTEM.md
│   └── ... (other documentation files)
│
├── data/                 # Data files
│   ├── database.csv
│   └── admin_data.json
│
├── static/              # Static files
│   └── chat.html
│
└── logs/                # Application logs

```

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the application:**
   - **Linux/Mac:** `./scripts/deployment/start.sh`
   - **Windows:** `scripts\RUN_PROJECT.bat`

4. **Run tests:**
   ```bash
   python tests/test_chatbot.py
   ```

## Key Changes from Previous Structure

- **Organized source code** into logical modules (api, core, models, handlers, utils)
- **Separated tests** from source code
- **Centralized documentation** in docs/ folder
- **Grouped scripts** by purpose (deployment, health checks)
- **Clear configuration** management in config/ folder
- **Static assets** in dedicated folder

## Development Guidelines

- All source code goes in `src/`
- All tests go in `tests/`
- Document new features in `docs/`
- Keep root directory clean (only essential config files)
- Use environment variables for sensitive data (never commit .env)

## Import Path Updates

With the new structure, you may need to update import statements:

**Old:**
```python
from chatbot import Chatbot
from ai_model import AIModel
```

**New:**
```python
from src.core.chatbot import Chatbot
from src.models.ai_model import AIModel
```

Consider adding the project root to PYTHONPATH or using relative imports.
