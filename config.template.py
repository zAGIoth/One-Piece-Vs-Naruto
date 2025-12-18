# config.py
# USER CONFIGURATION
# Set your API keys, Model IDs, and Base URLs here.

# =============================================================================
# API CONFIGURATION
# =============================================================================

# OPTION 1: OpenRouter (Default)
BASE_URL = "https://openrouter.ai/api/v1"
# Generator: Creates ideas and generates responses
MODEL_ID_GENERATOR = "deepseek/deepseek-v3.2"
# Auditor: Verifies and audits generated ideas  
MODEL_ID_AUDITOR = "anthropic/claude-haiku-4.5"

# OPTION 2: OpenAI (Uncomment to use - Untested)
# BASE_URL = "https://api.openai.com/v1"
# MODEL_ID_GENERATOR = "gpt-4o"
# MODEL_ID_AUDITOR = "gpt-4o-mini"

# OPTION 3: Local / Other (Uncomment to use - Untested)
# Warning: ThinkTwice requires high instruction-following capabilities.
# BASE_URL = "http://localhost:11434/v1"
# MODEL_ID_GENERATOR = "llama3:70b"
# MODEL_ID_AUDITOR = "llama3:8b"

# =======================================================================
# AUTHENTICATION
# ======================================================================

# Enter your API Key here. 
API_KEY = "..."