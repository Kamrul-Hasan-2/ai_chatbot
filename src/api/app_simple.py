"""
Compatibility wrapper for MVC controller entrypoint.
Keeps legacy import path: src.api.app_simple
"""

from src.controllers.chat_controller import app, initialize
from src.api.webchat_routes import webchat_bp, webchat_docs_bp

app.register_blueprint(webchat_bp)
app.register_blueprint(webchat_docs_bp)
