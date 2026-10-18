import logging
from typing import Optional, Dict, Any
import requests
from config import OLLAMA_HOST, OLLAMA_MODEL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL):
        self.host = host
        self.model = model

    def ensure_running(self) -> bool:
        """Ensure Ollama daemon is running. If not, auto-start in background without window."""
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=1.0)
            if res.status_code == 200:
                return True
        except Exception:
            pass

        import os
        import subprocess
        import time

        logger.info("Ollama is not running. Auto-starting 'ollama serve' in background...")
        ollama_bin = "ollama"
        user_home = os.environ.get("USERPROFILE", "")
        standard_ollama = os.path.join(user_home, "AppData", "Local", "Programs", "Ollama", "ollama.exe")
        if os.path.exists(standard_ollama):
            ollama_bin = standard_ollama

        try:
            creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
            subprocess.Popen(
                [ollama_bin, "serve"],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            for _ in range(15):
                time.sleep(0.4)
                try:
                    res = requests.get(f"{self.host}/api/tags", timeout=1.0)
                    if res.status_code == 200:
                        logger.info("Ollama service successfully auto-started in background.")
                        return True
                except Exception:
                    pass
        except Exception as e:
            logger.error("Failed to auto-start Ollama: %s", e)
        return False

    def check_health(self) -> Dict[str, Any]:
        """Check if Ollama is accessible and whether the target model exists."""
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=1.5)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_exists = any(
                    self.model in m or m.startswith(self.model)
                    for m in models
                )
                return {
                    "connected": True,
                    "model_available": model_exists,
                    "available_models": models,
                }
        except Exception:
            pass

        # If not running, attempt auto-starting silently
        if self.ensure_running():
            try:
                res = requests.get(f"{self.host}/api/tags", timeout=2.0)
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model_exists = any(
                        self.model in m or m.startswith(self.model)
                        for m in models
                    )
                    return {
                        "connected": True,
                        "model_available": model_exists,
                        "available_models": models,
                    }
            except Exception:
                pass

        return {
            "connected": False,
            "model_available": False,
            "available_models": [],
        }

    def get_gpu_specs(self) -> Dict[str, Any]:
        """
        Dynamically detects hardware GPU capabilities using nvidia-smi,
        PyTorch CUDA, or CPU fallback.
        """
        import os
        import subprocess

        # 1. Direct hardware query via nvidia-smi (fastest & most accurate for NVIDIA on Windows)
        try:
            out = subprocess.check_output(
                'nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits',
                shell=True, text=True, stderr=subprocess.DEVNULL
            ).strip()
            if out:
                line = out.splitlines()[0]
                parts = [p.strip() for p in line.split(',')]
                name = parts[0]
                total_mb = float(parts[1])
                free_mb = float(parts[2])
                tier = "high" if total_mb >= 7800 else ("mid" if total_mb >= 3800 else "entry")
                return {
                    "name": name,
                    "total_mb": total_mb,
                    "free_mb": free_mb,
                    "tier": tier,
                    "source": "nvidia-smi"
                }
        except Exception:
            pass

        # 2. PyTorch CUDA fallback
        try:
            import torch
            if torch.cuda.is_available():
                free_b, total_b = torch.cuda.mem_get_info()
                name = torch.cuda.get_device_name(0)
                total_mb = total_b / (1024 ** 2)
                free_mb = free_b / (1024 ** 2)
                tier = "high" if total_mb >= 7800 else ("mid" if total_mb >= 3800 else "entry")
                return {
                    "name": name,
                    "total_mb": total_mb,
                    "free_mb": free_mb,
                    "tier": tier,
                    "source": "torch.cuda"
                }
        except Exception:
            pass

        # 3. CPU / Integrated Graphics fallback
        return {
            "name": "CPU / Integrated Graphics",
            "total_mb": 0,
            "free_mb": 0,
            "tier": "entry",
            "source": "cpu"
        }

    def get_dynamic_inference_config(self) -> Dict[str, Any]:
        """
        Calculates optimal Ollama runtime parameters based on detected GPU tier:
        - High-tier GPU (>=8GB VRAM): 16K context, 1024 batch size, 99 GPU layers, 30m keep-alive.
        - Mid-tier GPU (4GB-8GB VRAM): 8K context, 512 batch size, 99 GPU layers, 15m keep-alive.
        - Low-tier / CPU fallback (<4GB): 4K context, 256 batch size, optimal CPU threads, 5m keep-alive.
        """
        import os
        specs = self.get_gpu_specs()
        tier = specs["tier"]

        if tier == "high":
            # High-end discrete GPU (RTX 3070/3080/4070/4080/4090, 8GB-24GB)
            options = {
                "temperature": 0.2,
                "num_predict": 1536,
                "num_ctx": 16384,
                "num_batch": 1024,
                "num_gpu": 99,
                "f16_kv": True,
            }
            keep_alive = "30m"
        elif tier == "mid":
            # Mid-range discrete GPU (RTX 2050/3050/3060/4050/4060, 4GB-8GB)
            options = {
                "temperature": 0.2,
                "num_predict": 1536,
                "num_ctx": 8192,
                "num_batch": 512,
                "num_gpu": 99,
                "f16_kv": True,
            }
            keep_alive = "15m"
        else:
            # Low VRAM or CPU fallback
            optimal_threads = min(8, max(2, os.cpu_count() or 4))
            options = {
                "temperature": 0.2,
                "num_predict": 1536,
                "num_ctx": 4096,
                "num_batch": 256,
                "num_thread": optimal_threads,
            }
            keep_alive = "5m"

        return {
            "options": options,
            "keep_alive": keep_alive,
            "specs": specs
        }

    def get_optimal_num_ctx(self) -> int:
        """Backward-compatible helper returning context window size."""
        config = self.get_dynamic_inference_config()
        return config["options"].get("num_ctx", 4096)

    def generate(self, prompt: str, system: Optional[str] = None, format_json: bool = True) -> str:
        """Send a generation request to Ollama with dynamic GPU memory acceleration."""
        self.ensure_running()
        dyn_config = self.get_dynamic_inference_config()
        options = dyn_config["options"]
        keep_alive = dyn_config["keep_alive"]

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": options,
        }
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        try:
            res = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            res.raise_for_status()
            data = res.json()
            return data.get("response", "").strip()
        except requests.exceptions.ConnectionError as ce:
            logger.error("Ollama connection error: %s", ce)
            raise ConnectionError(f"Could not connect to Ollama at {self.host}.") from ce
        except requests.exceptions.Timeout as te:
            logger.error("Ollama request timed out: %s", te)
            raise TimeoutError(f"Ollama took longer than {REQUEST_TIMEOUT}s to respond.") from te
        except Exception as ex:
            logger.error("Ollama generation error: %s", ex)
            raise

    def warm_up(self) -> bool:
        """
        Pre-load the model into GPU VRAM with a 1-token query.
        Ensures Ollama is running, starts it if not, and sends a fast warmup.
        """
        import os
        import subprocess
        import time

        health = self.check_health()
        if not health["connected"]:
            logger.info("Ollama is not running. Launching 'ollama serve' in background...")
            ollama_bin = "ollama"
            user_home = os.environ.get("USERPROFILE", "")
            standard_ollama = os.path.join(user_home, "AppData", "Local", "Programs", "Ollama", "ollama.exe")
            if os.path.exists(standard_ollama):
                ollama_bin = standard_ollama

            try:
                creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
                subprocess.Popen(
                    [ollama_bin, "serve"],
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                for _ in range(12):
                    time.sleep(0.5)
                    health = self.check_health()
                    if health["connected"]:
                        logger.info("Ollama service successfully started.")
                        break
            except Exception as e:
                logger.error("Failed to auto-start Ollama: %s", e)

        try:
            dyn_config = self.get_dynamic_inference_config()
            options = dict(dyn_config.get("options", {}))
            options["num_predict"] = 1
            keep_alive = dyn_config.get("keep_alive", "30m")
            payload = {
                "model": self.model,
                "prompt": "hi",
                "stream": False,
                "keep_alive": keep_alive,
                "options": options
            }
            logger.info("Warming up Ollama model '%s' in GPU VRAM (keep_alive=%s)...", self.model, keep_alive)
            res = requests.post(f"{self.host}/api/generate", json=payload, timeout=max(180.0, REQUEST_TIMEOUT))
            if res.status_code == 200:
                logger.info("Ollama model '%s' successfully warmed up in VRAM.", self.model)
                return True
            else:
                logger.warning("Ollama warm-up returned status %s: %s", res.status_code, res.text)
                return False
        except Exception as e:
            logger.warning("Ollama warm-up error: %s", e)
            return False
