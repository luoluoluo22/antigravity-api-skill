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
            print("[-] Error: Configuration missing base_url or api_key", file=sys.stderr)
            sys.exit(1)
            
    def _load_config(self):
        # [Fix] 支持 PyInstaller 打包后的路径
        if getattr(sys, 'frozen', False):
            # 1. 优先读取 EXE 同级目录下的 data/config.json (用户可配置)
            exe_dir = Path(sys.executable).parent
            user_config = exe_dir / "data" / "config.json"
            if user_config.exists():
                try: 
                    return json.loads(user_config.read_text(encoding='utf-8'))
                except: pass
            
            # 2. 读取内部打包的资源 (如果配置了 _MEIPASS)
            internal_config = Path(sys._MEIPASS) / "data" / "config.json"
            if internal_config.exists():
                try: return json.loads(internal_config.read_text(encoding='utf-8'))
                except: pass

        current_dir = Path(__file__).parent
        config_path = current_dir / "data" / "config.json"
        
        if not config_path.exists():
            # 尝试在当前工作目录找
            cwd_config = Path.cwd() / "data" / "config.json"
            if cwd_config.exists():
                config_path = cwd_config
            else:
                print(f"[-] Config not found at {config_path}", file=sys.stderr)
                return {}
            
        try:
            return json.loads(config_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"[-] Error parsing config: {e}", file=sys.stderr)
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
            print(f"[*] Using cached optimized video: {output_path}", file=sys.stderr)
            return str(output_path)
        
        print(f"[*] Optimizing video for AI analysis: {os.path.basename(input_path)}...", file=sys.stderr)
        
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
            print(f"[*] Starting Smart Compression (Target: 360p@5fps)...", file=sys.stderr)
            
            # Try GPU first
            try:
                print(f"[*] Attempting GPU acceleration (h264_nvenc) at 10fps...", file=sys.stderr)
                simple_gpu_cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-c:v', 'h264_nvenc', '-preset', 'fast', '-cq', '38',
                    '-vf', 'scale=-2:360,fps=10', 
                    '-an',
                    str(output_path)
                ]
                subprocess.run(simple_gpu_cmd, stdout=subprocess.DEVNULL, check=True)
            except Exception as e:
                print(f"[-] GPU failed, switching to CPU (10fps compression): {e}", file=sys.stderr)
                cmd_cpu_ultra = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-vf', 'scale=-2:360,fps=10',
                    '-vcodec', 'libx264', '-crf', '35', '-preset', 'ultrafast',
                    '-an',
                    str(output_path)
                ]
                subprocess.run(cmd_cpu_ultra, stdout=subprocess.DEVNULL, check=True)
            
            new_size = os.path.getsize(output_path)
            print(f"[+] Optimization complete: {new_size/1024/1024:.2f}MB", file=sys.stderr)
            return str(output_path)
        except Exception as e:
            print(f"[-] Optimization failed: {e}", file=sys.stderr)
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

        print(f"[*] Uploading {file_name} ({file_size/1024/1024:.2f}MB)...", file=sys.stderr)
        
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
                    print(f"[-] Mode 1 failed ({response.status_code}) for {url}: {response.text[:100]}", file=sys.stderr)
                
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
                    print(f"[-] Mode 2 failed ({response.status_code}) for {url}: {response.text[:100]}", file=sys.stderr)
                        
            except Exception as e:
                print(f"[-] Attempt failed for {url}: {e}", file=sys.stderr)
                
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
            
            # Smart optimization: if it's a video and > 10MB, compress it first
            is_video = path.lower().endswith(('.mp4', '.mov', '.webm'))
            file_size = os.path.getsize(path)
            
            working_path = path
            if is_video and file_size > 10 * 1024 * 1024:
                working_path = self._optimize_video(path)
            
            # All media sent via Base64 for maximum compatibility
            try:
                mime_type, _ = mimetypes.guess_type(working_path)
                mime_type = mime_type or "application/octet-stream"
                if is_video: mime_type = "video/mp4" # Ensure video mime type
                
                print(f"[*] Encoding media (Base64): {os.path.basename(working_path)}", file=sys.stderr)
                with open(working_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("utf-8")
                
                multimodal_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
                })
            except Exception as e:
                print(f"[-] Failed to process {path}: {e}", file=sys.stderr)

        if multimodal_content and messages and messages[-1]['role'] == 'user':
            original_text = messages[-1]['content']
            # Avoid nesting if it's already a list from a previous attempt
            if isinstance(original_text, list):
                # Check if it already has multimodal items to avoid duplicates
                existing_types = [item.get("type") for item in original_text if isinstance(item, dict)]
                if "image_url" not in existing_types:
                    original_text.extend(multimodal_content)
            else:
                new_content = [{"type": "text", "text": original_text}]
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
            print(f"[*] Sending Payload ({len(json.dumps(payload))/1024/1024:.1f}MB) to {url}...", file=sys.stderr)
            print("[*] Please wait, this may take a minute for large videos...", file=sys.stderr)
            response = s.post(url, headers=headers, json=payload, stream=True, timeout=900) 
            
            # --- 自动降级逻辑 (Fallback) ---
            # 如果请求的是 gemini-3-pro 且返回 503 (账号故障/负载过高)
            if response.status_code == 503 and model == "gemini-3-pro":
                print(f"[!] gemini-3-pro 返回 503 (繁忙/账号故障)，正在自动切换到 gemini-3-flash 进行重试...", file=sys.stderr)
                payload["model"] = "gemini-3-flash"
                response = s.post(url, headers=headers, json=payload, stream=True, timeout=900)
            
            print(f"[*] Response received: {response.status_code}", file=sys.stderr)
            return response
        except Exception as e:
            print(f"[-] Request failed: {e}", file=sys.stderr)
            return None

    def generate_image(self, prompt, size="1024x1024", image_path=None, quality="standard", n=1):
        # According to the provided SDK, images are generated via the /chat/completions endpoint
        url = f"{self.base_url}/chat/completions"
        model = self.config.get("default_image_model", "gemini-3-pro-image")
        
        messages = []
        if image_path and os.path.exists(image_path):
            print(f"[*] Encoding reference image: {image_path}", file=sys.stderr)
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
                print(f"[-] Failed to read image: {e}", file=sys.stderr)
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
        
        print(f"[*] Sending Image Request via Chat API to {model}...", file=sys.stderr)
        try:
            response = s.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[-] API Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"[-] Image Request failed: {e}", file=sys.stderr)
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
            print(f"[-] Models Request failed: {e}", file=sys.stderr)
            return []
