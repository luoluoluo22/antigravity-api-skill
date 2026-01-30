import sys
import os
import json
from pathlib import Path

# Add libs to path
current_dir = Path(__file__).parent
libs_path = current_dir.parent / "libs"
sys.path.append(str(libs_path))

try:
    from api_client import AntigravityClient
except ImportError:
    print("[-] Error: libs module not found")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python chat.py \"Your prompt here\" [model_name]")
        return

    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else None
    
    client = AntigravityClient()
    
    messages = [{"role": "user", "content": prompt}]
    
    print(f"[*] Asking {model or client.config.get('default_chat_model')}...")
    
    response = client.chat_completion(messages, model=model)
    
    if not response:
        return

    full_content = ""
    print("\nStarting response stream:\n" + "-"*30)
    
    # Simple SSE parser
    for line in response.iter_lines():
        if not line: continue
        line_str = line.decode('utf-8')
        if line_str.startswith("data: "):
            data_str = line_str[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    print(content, end="", flush=True)
                    full_content += content
            except:
                pass
                
    print("\n" + "-"*30 + "\n[Done]")

if __name__ == "__main__":
    main()
