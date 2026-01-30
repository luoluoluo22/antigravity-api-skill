import json
import os
import sys
from pathlib import Path
import requests

# Globally disable proxies to prevent localhost connection issues
s = requests.Session()
s.trust_env = True


class AntigravityClient:
    def __init__(self):
        self.config = self._load_config()
        self.base_url = self.config.get("base_url", "").rstrip("/")
        self.api_key = self.config.get("api_key", "")
        
        if not self.base_url or not self.api_key:
            print("[-] Error: Configuration missing base_url or api_key")
            sys.exit(1)
            
    def _load_config(self):
        current_dir = Path(__file__).parent
        config_path = current_dir / "data" / "config.json"
        
        if not config_path.exists():
            print(f"[-] Config not found at {config_path}")
            return {}
            
        try:
            return json.loads(config_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"[-] Error parsing config: {e}")
            return {}

    def chat_completion(self, messages, model=None, temperature=0.7):
        url = f"{self.base_url}/chat/completions"
        model = model or self.config.get("default_chat_model", "claude-sonnet-4-5")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        # Mimic the working script's headers, plus a compliant User-Agent just in case
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity/4.0.6" 
        }
        
        try:
            # Using standard requests with stream=True
            response = s.post(url, headers=headers, json=payload, stream=True, timeout=60)
            return response
        except Exception as e:
            print(f"[-] Request failed: {e}")
            return None

    def generate_image(self, prompt, size="1024x1024", quality="standard", n=1):
        url = f"{self.base_url}/images/generations"
        model = self.config.get("default_image_model", "gemini-3-pro-image")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": n,
            "response_format": "b64_json"
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity/4.0.6"
        }
        
        print(f"[*] Sending Image Request to {model}...")
        try:
            response = s.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[-] API Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"[-] Image Request failed: {e}")
            return None

    def get_models(self):
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Antigravity/4.0.6"
        }
        
        try:
            response = s.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Unified parsing: some APIs return {'data': [...]}, some return list directly
                if isinstance(data, dict) and 'data' in data:
                    return data['data']
                elif isinstance(data, list):
                    return data
                return []
            else:
                print(f"[-] API Error {response.status_code}: {response.text}")
                return []
        except Exception as e:
            print(f"[-] Models Request failed: {e}")
            return []
