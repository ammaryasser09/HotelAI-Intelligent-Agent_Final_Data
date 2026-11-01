import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-3.8-live"
THINKING_LEVEL = "low"
ACCOUNT_ID = 997