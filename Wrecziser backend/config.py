import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "prompts" / "summarizer.txt"

# Ollama Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M")

# Server Configuration
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Request Limits
MAX_CONTENT_CHARS = int(os.getenv("MAX_CONTENT_CHARS", "8000"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "240.0"))
