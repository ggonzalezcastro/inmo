
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load env from .env file
load_dotenv()

print("Testing Gemini Configuration...")
api_key = os.getenv("GEMINI_API_KEY")
model_name = "gemini-2.0-flash"

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in environment")
    sys.exit(1)

print(f"API Key found: {api_key[:5]}...{api_key[-5:]}")
print(f"Model: {model_name}")

try:
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    print("Client initialized.")
    
    print(f"Attempting to generate content with model {model_name}...")
    
    response = client.models.generate_content(
        model=model_name,
        contents="Hello, this is a test.",
    )
    
    print("Success!")
    print(f"Response: {response.text}")

except Exception as e:
    print(f"ERROR: {str(e)}")
    print(f"Error type: {type(e).__name__}")
    if hasattr(e, 'response'):
        print(f"Response details: {e.response}")
