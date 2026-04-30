"""
Compatibility wrapper for MVC controller entrypoint.
Keeps legacy import path: src.api.app_simple
"""

from src.controllers.chat_controller import app, initialize
