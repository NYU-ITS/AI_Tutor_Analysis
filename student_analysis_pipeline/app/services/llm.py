import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://ai-gateway.apps.cloud.rt.nyu.edu/v1")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")

MODEL_MAP = {
    "gpt-4o": "@gpt-4o/gpt-4o",
    "gpt-4o-mini": "@gpt-4o-mini/gpt-4o-mini",
}

# Default Portkey model id sent in the API payload (see MODEL_MAP).
DEFAULT_MODEL = "gpt-4o-mini"


def chat(messages: list, model: str = DEFAULT_MODEL, temperature: float = 0.0, max_retries: int = 3, **kwargs) -> str:
    model_id = MODEL_MAP.get(model, model)

    headers = {
        "x-portkey-api-key": PORTKEY_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        **kwargs,
    }

    last_error = None

    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{PORTKEY_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=180,
            )
            response.raise_for_status()

            result = response.json()["choices"][0]["message"]["content"]
            if not result or result.strip() == "":
                raise ValueError("Empty response from API")
            return result

        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = f"Attempt {attempt + 1}/{max_retries}: {e}"
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise Exception(f"LLM call failed after {max_retries} attempts. Last error: {last_error}")


def ask(prompt: str, model: str = DEFAULT_MODEL, system: str = None, **kwargs) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, model=model, **kwargs)


def ask_with_images(prompt: str, image_urls: list[dict], model: str = DEFAULT_MODEL, system: str = None, **kwargs) -> str:
    """Send a prompt with inline base64 images to a vision-capable model.

    image_urls: list of dicts like {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    content = [{"type": "text", "text": prompt}] + image_urls
    messages.append({"role": "user", "content": content})

    return chat(messages, model=model, **kwargs)
