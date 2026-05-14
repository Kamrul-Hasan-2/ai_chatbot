"""
Shared pytest setup — adds project root and src/ to sys.path so tests
can `from services.intent_service import ...` exactly like the running app.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")

for p in (PROJECT_ROOT, SRC_PATH):
    if p not in sys.path:
        sys.path.insert(0, p)
