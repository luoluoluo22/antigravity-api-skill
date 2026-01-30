import sys
import os
import time
import base64
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
        print("Usage: python generate_image.py \"Prompt\" [size]")
        print("Examples: python generate_image.py \"A cat\" \"16:9\"")
        return

    prompt = sys.argv[1]
    # Handle simple aspect ratios mapped to approximate pixels if needed, 
    # but Antigravity docs say it handles 16:9 string directly? 
    # Wait, docs say: "size": "1920x1080" maps to 16:9. 
    # Docs also say: "gemini-3-pro-image-16-9-4k" model suffix.
    # Let's support both raw size and intelligent mapping.
    
    size_arg = sys.argv[2] if len(sys.argv) > 2 else "1024x1024"
    
    # Simple mapping if user provides ratio
    ratio_map = {
        "16:9": "1920x1080",
        "9:16": "1080x1920", 
        "4:3": "1024x768",
        "1:1": "1024x1024"
    }
    
    target_size = ratio_map.get(size_arg, size_arg)
    
    client = AntigravityClient()
    
    res = client.generate_image(prompt, size=target_size, quality="hd")
    
    if res and "data" in res:
        # Save images
        save_dir = Path(os.getcwd()) / "generated_assets"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        for i, item in enumerate(res["data"]):
            b64 = item.get("b64_json")
            if b64:
                img_data = base64.b64decode(b64)
                fname = f"antigravity_{int(time.time())}_{i}.png"
                save_path = save_dir / fname
                save_path.write_bytes(img_data)
                print(f"[+] Image saved: {save_path}")
    else:
        print("[-] Generation failed")

if __name__ == "__main__":
    main()
