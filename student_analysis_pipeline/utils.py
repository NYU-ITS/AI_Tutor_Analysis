import requests
import json
import time

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://ai-gateway.apps.cloud.rt.nyu.edu/v1")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")

if not PORTKEY_API_KEY:
    print("WARNING: PORTKEY_API_KEY not found in environment or .env file")


        

def ask(prompt: str, model: str = "gpt-4o", system: str = None, **kwargs) -> str:
    """
    Simple one-shot question to LLM.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    return chat(messages, model=model, **kwargs)

def chat(messages: list, model: str = "gpt-4o", temperature: float = 0.0, max_retries: int = 3, **kwargs) -> str:
    """
    Send a chat completion request using requests library.
    Retries up to max_retries times on failure.
    """
    # Map friendly model names to Portkey model IDs
    model_id = model
    if model == "gpt-4o":
        model_id = "@gpt-4o/gpt-4o"
    elif model == "gpt-4o-mini":
        model_id = "@gpt-4o-mini/gpt-4o-mini"
        
    headers = {
        "x-portkey-api-key": PORTKEY_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        **kwargs
    }
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{PORTKEY_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()["choices"][0]["message"]["content"]
            
            # Verify we got actual content
            if not result or result.strip() == "":
                raise ValueError("Empty response from API")
                
            return result
            
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout on attempt {attempt + 1}/{max_retries}: {e}"
            print(last_error)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                
        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP error on attempt {attempt + 1}/{max_retries}: {e}"
            print(last_error)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = f"Response parsing error on attempt {attempt + 1}/{max_retries}: {e}"
            print(last_error)
            if 'response' in locals():
                print(f"Response text: {response.text[:500]}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        except Exception as e:
            last_error = f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}"
            print(last_error)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    # If we've exhausted all retries, raise an exception
    raise Exception(f"Failed to get response from Portkey API after {max_retries} attempts. Last error: {last_error}")
