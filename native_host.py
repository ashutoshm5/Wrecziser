import sys
import struct
import json
import subprocess
import os
import urllib.request

def send_message(msg):
    try:
        data = json.dumps(msg).encode("utf-8")
        sys.stdout.buffer.write(struct.pack("<I", len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except Exception:
        pass

def read_message():
    try:
        raw_len = sys.stdin.buffer.read(4)
        if len(raw_len) < 4:
            return None
        msg_len = struct.unpack("<I", raw_len)[0]
        raw_data = sys.stdin.buffer.read(msg_len)
        return json.loads(raw_data.decode("utf-8"))
    except Exception:
        return None

def is_backend_running():
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health")
        with urllib.request.urlopen(req, timeout=0.5) as r:
            return r.status == 200
    except Exception:
        return False

def start_backend():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "Wrecziser backend")
    vbs_launcher = os.path.join(backend_dir, "run_backend_silent.vbs")
    DETACHED_PROCESS = 0x00000008
    CREATE_NO_WINDOW = 0x08000000

    if not is_backend_running():
        try:
            subprocess.Popen(
                ["wscript.exe", vbs_launcher],
                cwd=backend_dir,
                creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            python_exe = os.path.join(backend_dir, ".venv", "Scripts", "python.exe")
            if not os.path.exists(python_exe):
                python_exe = "python"
            main_py = os.path.join(backend_dir, "main.py")
            subprocess.Popen(
                [python_exe, main_py],
                cwd=backend_dir,
                creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    # Also ensure Ollama service is up
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=0.5) as r:
            pass
    except Exception:
        ollama_bin = "ollama"
        user_home = os.environ.get("USERPROFILE", "")
        standard_ollama = os.path.join(user_home, "AppData", "Local", "Programs", "Ollama", "ollama.exe")
        if os.path.exists(standard_ollama):
            ollama_bin = standard_ollama
        try:
            subprocess.Popen(
                [ollama_bin, "serve"],
                creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

def main():
    _ = read_message()
    start_backend()
    send_message({"status": "ok", "started": True})

if __name__ == "__main__":
    main()
