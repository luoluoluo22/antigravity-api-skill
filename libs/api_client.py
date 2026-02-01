import json
import os
import sys
from pathlib import Path
import requests
import base64
import mimetypes
import subprocess
import tempfile
import time

# Globally disable proxies to prevent localhost connection issues
s = requests.Session()
s.trust_env = False


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

    def _optimize_video(self, input_path):
        """
        Use FFmpeg to compress large videos to a manageable size for AI.
        Target: 360P at low bitrate, keeping timing intact.
        Saves to ./antigravity_cache to Allow reuse.
        """
        # Save to current working directory cache instead of temp
        cache_dir = Path("video_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Consistent naming for caching based on modification time and name
        mtime = int(os.path.getmtime(input_path))
        safe_name = os.path.basename(input_path).replace(" ", "_")
        output_path = cache_dir / f"optimized_{mtime}_{safe_name}"
        
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"[*] Using cached optimized video: {output_path}")
            return str(output_path)
        
        print(f"[*] Optimizing video for AI analysis: {os.path.basename(input_path)}...")
        
        # FFmpeg command optimized for extreme compression + GPU (if available)
        # Try to use NVIDIA GPU (h264_nvenc) first, fallback to CPU (libx264)
        
        common_filters = [
            '-vf', 'scale=-2:360,fps=5', # Downscale to 360p, reduce FPS to 5
            '-an', # Remove audio completely (optional: keep if audio analysis needed, but -an saves size)
        ]
        
        # GPU Command (NVIDIA)
        cmd_gpu = [
            'ffmpeg', '-y', 
            '-hwaccel', 'cuda', 
            '-hwaccel_output_format', 'cuda',
            '-i', input_path,
            '-c:v', 'h264_nvenc', # Use NVIDIA Encoder
            '-preset', 'p1',      # Fastest preset
            '-qp', '35',          # Quality parameter (higher = lower quality)
            '-vf', 'scale_cuda=-2:360,fps=5', # CUDA-accelerated scaling
            '-an', 
            str(output_path)
        ]
        
        # CPU Command (Fallback)
        cmd_cpu = [
            'ffmpeg', '-y', '-i', input_path,
            '-vf', 'scale=-2:360,fps=5',
            '-vcodec', 'libx264', '-crf', '35', '-preset', 'ultrafast',
            '-an', # Removing audio for visual analysis tasks to save huge space
            str(output_path)
        ]

        try:
            print(f"[*] Starting Smart Compression (Target: 360p@5fps)...")
            
            # Try GPU first
            try:
                print(f"[*] Attempting GPU acceleration (h264_nvenc)...")
                # Need to remove filter from GPU command if complex filters aren't supported with hwaccel in this build
                # Using a simpler GPU command for stability
                simple_gpu_cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-c:v', 'h264_nvenc', '-preset', 'fast', '-cq', '35',
                    '-vf', 'scale=-2:360,fps=5', 
                    '-an',
                    str(output_path)
                ]
                subprocess.run(simple_gpu_cmd, stdout=subprocess.DEVNULL, check=True)
            except Exception as e:
                print(f"[-] GPU failed, switching to CPU: {e}")
                subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, check=True)
            
            new_size = os.path.getsize(output_path)
            print(f"[+] Optimization complete: {new_size/1024/1024:.2f}MB")
            return str(output_path)
        except Exception as e:
            print(f"[-] Optimization failed: {e}")
            return input_path # Fallback to original

    def upload_file(self, file_path):
        """
        Stream large files to the server using the /files endpoint.
        Try multiple formats and endpoints for compatibility.
        """
        if not os.path.exists(file_path):
            return None
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        
        if file_path.lower().endswith(('.mp4', '.mov', '.webm')):
            mime_type = mime_type if "video" in mime_type else "video/mp4"

        print(f"[*] Uploading {file_name} ({file_size/1024/1024:.2f}MB)...")
        
        # Try a few common endpoints
        endpoints = [f"{self.base_url}/files"]
        if "/v1" in self.base_url:
            endpoints.append(self.base_url.replace("/v1", "") + "/files")
            endpoints.append(self.base_url.replace("/v1", "/upload/v1") + "/files")
            endpoints.append(self.base_url.replace("/v1", "/upload/v1beta") + "/files")
            
        for url in endpoints:
            try:
                # Mode 1: Multipart (Standard OpenAI compatible)
                with open(file_path, "rb") as f:
                    files = {
                        'file': (file_name, f, mime_type),
                        'purpose': (None, 'fine-tune')
                    }
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    response = s.post(url, headers=headers, files=files, timeout=600)
                
                if response.status_code == 200:
                    result = response.json()
                    file_uri = result.get("file_uri") or result.get("id") or result.get("uri")
                    if file_uri:
                        print(f"[+] Upload success: {file_uri}")
                        return {"uri": file_uri, "mime_type": mime_type}
                else:
                    print(f"[-] Mode 1 failed ({response.status_code}) for {url}: {response.text[:100]}")
                
                # Mode 2: Octet-stream
                with open(file_path, "rb") as f:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "X-File-Name": file_name,
                        "X-File-Type": mime_type,
                        "Content-Type": "application/octet-stream"
                    }
                    response = s.post(url, headers=headers, data=f, timeout=600)
                
                if response.status_code == 200:
                    result = response.json()
                    file_uri = result.get("file_uri") or result.get("uri")
                    if file_uri:
                        print(f"[+] Upload success: {file_uri}")
                        return {"uri": file_uri, "mime_type": mime_type}
                else:
                    print(f"[-] Mode 2 failed ({response.status_code}) for {url}: {response.text[:100]}")
                        
            except Exception as e:
                print(f"[-] Attempt failed for {url}: {e}")
                
        return None

    def chat_completion(self, messages, model=None, temperature=0.7, file_paths=None, file_path=None):
        url = f"{self.base_url}/chat/completions"
        model = model or self.config.get("default_chat_model", "claude-sonnet-4-5")
        
        paths = []
        if file_path: paths.append(file_path)
        if file_paths:
            if isinstance(file_paths, list): paths.extend(file_paths)
            else: paths.append(file_paths)
            
        multimodal_content = []
        
        for path in paths:
            if not os.path.exists(path): continue
            
            # Smart optimization: if it's a video and > 20MB, compress it first
            is_video = path.lower().endswith(('.mp4', '.mov', '.webm'))
            file_size = os.path.getsize(path)
            
            working_path = path
            is_temp = False
            if is_video and file_size > 20 * 1024 * 1024:
                working_path = self._optimize_video(path)
                # Keep cache files, don't delete them
                is_temp = False 
            
            new_size = os.path.getsize(working_path)
            
            # Now use File API for the optimized file if it's still > 5MB
            if new_size > 5 * 1024 * 1024:
                file_info = self.upload_file(working_path)
                if file_info:
                    multimodal_content.append({
                        "type": "file_url",
                        "file_url": {"url": file_info["uri"], "mime_type": file_info["mime_type"]}
                    })
                    # if is_temp: os.remove(working_path) # Disabled deletion for cache reuse
                    continue
            
            # Final fallback to Base64
            try:
                mime_type, _ = mimetypes.guess_type(working_path)
                mime_type = mime_type or "application/octet-stream"
                if is_video: mime_type = mime_type if "video" in mime_type else "video/mp4"
                
                print(f"[*] Encoding media: {os.path.basename(working_path)}")
                b64_data = base64.b64encode(open(working_path, "rb").read()).decode("utf-8")
                multimodal_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
                })
                # if is_temp: os.remove(working_path) # Disabled deletion for cache reuse
            except Exception as e:
                print(f"[-] Failed to process {path}: {e}")

        if multimodal_content and messages and messages[-1]['role'] == 'user':
            original_text = messages[-1]['content']
            new_content = [{"type": "text", "text": original_text}] if isinstance(original_text, str) else original_text
            new_content.extend(multimodal_content)
            messages[-1]['content'] = new_content

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity/4.0.6" 
        }
        
        try:
            response = s.post(url, headers=headers, json=payload, stream=True, timeout=300) 
            return response
        except Exception as e:
            print(f"[-] Request failed: {e}")
            return None

    def generate_image(self, prompt, size="1024x1024", image_path=None, quality="standard", n=1):
        # According to the provided SDK, images are generated via the /chat/completions endpoint
        url = f"{self.base_url}/chat/completions"
        model = self.config.get("default_image_model", "gemini-3-pro-image")
        
        messages = []
        if image_path and os.path.exists(image_path):
            print(f"[*] Encoding reference image: {image_path}")
            try:
                mime_type, _ = mimetypes.guess_type(image_path)
                mime_type = mime_type or "image/png"
                img_data = base64.b64encode(open(image_path, "rb").read()).decode("utf-8")
                
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{img_data}"}
                        }
                    ]
                })
            except Exception as e:
                print(f"[-] Failed to read image: {e}")
                messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": prompt})

        # Mapping size for the chat endpoint structure
        payload = {
            "model": model,
            "messages": messages,
            "size": size, # Using extra_body logic as top level for simplicity in REST
            "stream": False # Getting full response usually contains the URL/Image Markdown
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity/4.0.6"
        }
        
        print(f"[*] Sending Image Request via Chat API to {model}...")
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
