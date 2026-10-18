import os
import sys
import urllib.request
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models" / "kokoro"
MODEL_PATH = MODEL_DIR / "kokoro-v1_0.pth"
MODEL_URL = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v1_0.pth"

def download_kokoro_weights():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 100_000_000:
        print(f"[OK] Kokoro weights already present at: {MODEL_PATH}")
        return

    print(f"Downloading Kokoro-82M weights (~327MB)...")
    print(f"From: {MODEL_URL}")
    print(f"To:   {MODEL_PATH}")
    
    def report_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100.0, downloaded / total_size * 100)
            sys.stdout.write(f"\rProgress: {percent:.1f}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook=report_hook)
        print("\n[OK] Kokoro weights downloaded successfully!")
    except Exception as e:
        print(f"\n[ERROR] Failed to download Kokoro weights: {e}")
        print("Note: The voice service will also auto-download weights on first use if an internet connection is available.")

def ensure_dependencies():
    for pkg in ["python-multipart>=0.0.9", "en-core-web-sm==3.8.0"]:
        try:
            if pkg.startswith("python-multipart"):
                import multipart
            elif pkg.startswith("en-core-web-sm"):
                import spacy
                spacy.load("en_core_web_sm")
        except Exception:
            try:
                import subprocess
                if pkg.startswith("en-core-web-sm"):
                    subprocess.run([sys.executable, "-m", "pip", "install", "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl", "--quiet"], check=False)
                else:
                    subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--quiet"], check=False)
            except Exception:
                pass

if __name__ == "__main__":
    ensure_dependencies()
    download_kokoro_weights()

