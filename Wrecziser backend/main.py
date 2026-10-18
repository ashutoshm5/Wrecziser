import sys
import os
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG = os.path.join(BASE_DIR, "crash.log")
BACKEND_LOG = os.path.join(BASE_DIR, "backend.log")

def handle_exception(exc_type, exc_value, exc_traceback):
    with open(CRASH_LOG, "a", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
sys.excepthook = handle_exception
import threading
threading.excepthook = lambda args: handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

# Safely handle stdout and stderr for headless / detached / pythonw execution
def _is_invalid_stream(stream):
    if stream is None:
        return True
    try:
        stream.write("")
        stream.flush()
        return False
    except Exception:
        return True

_backend_log_file = open(BACKEND_LOG, "a", encoding="utf-8", buffering=1)

if _is_invalid_stream(sys.stdout):
    sys.stdout = _backend_log_file
if _is_invalid_stream(sys.stderr):
    sys.stderr = _backend_log_file

# Safely redirect OS-level file descriptors 1 and 2 if invalid
try:
    log_fd = os.open(BACKEND_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.dup2(log_fd, 1)
    except Exception:
        pass
    try:
        os.dup2(log_fd, 2)
    except Exception:
        pass
except Exception:
    pass

# Self-healing dependency check before FastAPI route definitions
try:
    import multipart
except ImportError:
    try:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "python-multipart>=0.0.9", "--quiet"], check=False)
    except Exception:
        pass

import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(BACKEND_LOG, encoding="utf-8")
    ]
)

from pydantic import BaseModel, Field
from config import SERVER_HOST, SERVER_PORT, OLLAMA_MODEL
from schemas import SummarizeRequest, SummarizeResponse, HealthResponse
from ollama_client import OllamaClient
from summarizer import WebpageSummarizer
from voice_service import voice_service
from screener_service import ScreenerService
from document_extractor import extract_document_text

# Configure logging
logger = logging.getLogger("wreciser.backend")

# Initialize FastAPI application
app = FastAPI(
    title="Wrecz Webpage Summarizer Backend",
    version="1.0.0",
    description="Local backend service routing webpage summarization to Qwen3 via Ollama."
)

@app.on_event("startup")
async def startup_event():
    import threading
    logger.info("Initializing and warming up Kokoro voice engine in RAM on startup...")
    threading.Thread(target=voice_service.warm_up, daemon=True).start()
    logger.info("Initializing and warming up Ollama LLM in background on startup...")
    threading.Thread(target=ollama.warm_up, daemon=True).start()

@app.post("/api/ollama/warmup")
@app.get("/api/ollama/warmup")
def warmup_ollama_endpoint():
    """Trigger Ollama model warm-up in GPU VRAM asynchronously on demand."""
    import threading
    threading.Thread(target=ollama.warm_up, daemon=True).start()
    return {"status": "warming_up", "model": OLLAMA_MODEL}

# Enable CORS for local extension access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
ollama = OllamaClient()
summarizer = WebpageSummarizer(client=ollama)
screener = ScreenerService(client=ollama)

# In-memory store for the latest summarized page
LATEST_SUMMARY: Dict[str, Any] = {
    "title": "No summary generated yet",
    "url": "",
    "summary": "Click 'Summarise this page' in the Wreciser Chrome extension to generate a summary.",
    "key_points": [],
    "important_facts": [],
    "timestamp": None
}

# In-memory stores for LinkedIn & Resume screening
LATEST_LINKEDIN_PROFILE: Dict[str, Any] = {
    "candidate_name": "No profile analyzed yet",
    "headline": "",
    "location": "",
    "url": "",
    "executive_summary": "Use the LinkedIn Analyzer tool in the Wreciser extension while viewing a LinkedIn profile to extract candidate insights.",
    "skills": [],
    "experience_highlights": [],
    "recommended_roles": []
}

LATEST_RESUME_TARGET: Dict[str, Any] = {
    "title": "General Assessment",
    "url": "",
    "content": ""
}

LATEST_RESUME_ANALYSIS: Dict[str, Any] = {
    "score": None,
    "verdict": "No resume screened yet",
    "target_role": "",
    "how_is_resume": "Upload or paste a resume to screen and score it across the 4 key criteria.",
    "strong_points": [],
    "weak_points": [],
    "suggestions": [],
    "rewrites": []
}

@app.get("/", response_class=HTMLResponse)
def index_view():
    """Friendly dashboard in browser showing latest summary and server status."""
    key_points_html = "".join(f"<li>{kp}</li>" for kp in LATEST_SUMMARY.get("key_points", []))
    facts_html = "".join(f"<li>{f}</li>" for f in LATEST_SUMMARY.get("important_facts", []))

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Wreciser Backend Dashboard</title>
      <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; color: #333; }}
        .card {{ background: white; padding: 24px 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        h1 {{ font-size: 24px; margin-top: 0; color: #111; }}
        h2 {{ font-size: 18px; margin-top: 20px; border-bottom: 2px solid #eee; padding-bottom: 6px; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; background: #e6f4ea; color: #137333; font-size: 13px; font-weight: bold; }}
        ul {{ padding-left: 20px; line-height: 1.6; }}
        li {{ margin-bottom: 6px; }}
        p {{ line-height: 1.6; }}
        .source-url {{ color: #1a73e8; word-break: break-all; font-size: 14px; text-decoration: none; }}
        .empty-note {{ color: #888; font-style: italic; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Wreciser Summarizer Backend <span class="badge">Running</span></h1>
        <p><strong>Model:</strong> {OLLAMA_MODEL}</p>
        <p><strong>Endpoint:</strong> <code>POST http://127.0.0.1:{SERVER_PORT}/summarize</code></p>
      </div>

      <div class="card">
        <h1>Latest Summarized Page</h1>
        <h2>{LATEST_SUMMARY.get('title', 'None')}</h2>
        {f'<p><a class="source-url" href="{LATEST_SUMMARY.get("url")}" target="_blank">{LATEST_SUMMARY.get("url")}</a></p>' if LATEST_SUMMARY.get("url") else ''}

        <h2>Executive Summary</h2>
        <p>{LATEST_SUMMARY.get('summary', 'No summary available.')}</p>

        <h2>Key Takeaways</h2>
        {f'<ul>{key_points_html}</ul>' if key_points_html else '<p class="empty-note">No key points yet.</p>'}

        <h2>Important Facts</h2>
        {f'<ul>{facts_html}</ul>' if facts_html else '<p class="empty-note">No facts yet.</p>'}
      </div>
    </body>
    </html>
    """

@app.get("/health", response_model=HealthResponse)
def get_health():
    """Health check verifying FastAPI, Ollama connectivity, and model availability."""
    health_info = ollama.check_health()
    return HealthResponse(
        status="healthy" if (health_info["connected"] and health_info["model_available"]) else "degraded",
        ollama_connected=health_info["connected"],
        model_available=health_info["model_available"],
        model_name=OLLAMA_MODEL,
    )

@app.get("/summarize")
def summarize_page_info():
    """GET endpoint so opening the URL in a browser returns clear info instead of 405 error."""
    return {
        "status": "active",
        "description": "This endpoint receives POST requests containing {title, url, content} from the Wreciser extension.",
        "latest_summary": LATEST_SUMMARY
    }

@app.post("/summarize", response_model=SummarizeResponse)
def summarize_page(request: SummarizeRequest):
    """Summarize webpage content using Qwen3 and return structured JSON."""
    global LATEST_SUMMARY

    if not request.content or len(request.content.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content is completely empty. Nothing to summarize."
        )

    # Check Ollama status before heavy request
    health = ollama.check_health()
    if not health["connected"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to local Ollama service at " + ollama.host
        )
    if not health["model_available"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Required model '{OLLAMA_MODEL}' is not installed in Ollama."
        )

    try:
        logger.info("Summarizing webpage: '%s' (%d chars)", request.title, len(request.content))
        result = summarizer.summarize(request)
        logger.info("Summarization successful for '%s'", request.title)

        # Store in latest summary cache
        LATEST_SUMMARY = {
            "title": result.title,
            "url": request.url,
            "summary": result.summary,
            "key_points": result.key_points,
            "important_facts": result.important_facts
        }

        return result
    except TimeoutError as te:
        logger.error("Timeout during summarization: %s", te)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Summarization timed out on the local model."
        )
    except ConnectionError as ce:
        logger.error("Connection lost to Ollama: %s", ce)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lost connection to Ollama."
        )
    except Exception as e:
        logger.exception("Failed to summarize webpage: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )

@app.get("/api/summary")
def get_wrecz_summary():
    """Retrieve the latest summarized page."""
    return LATEST_SUMMARY

@app.post("/api/summary")
def ingest_wrecz_summary(payload: dict):
    """
    Ingestion endpoint for 'Open in Wrecz'.
    Accepts the structured summary payload so extension sync succeeds.
    """
    global LATEST_SUMMARY
    logger.info("Received summary for Wrecz ingestion: %s", payload.get("title"))
    LATEST_SUMMARY = payload
    return {
        "status": "received",
        "title": payload.get("title"),
        "message": "Summary stored successfully for Wrecz Assistant."
    }

class VoiceSynthesisRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize using Kokoro voice")
    speed: Optional[float] = Field(default=0.94, description="Speaking speed rate (default 0.94)")

@app.post("/api/voice/synthesize")
def synthesize_voice(req: VoiceSynthesisRequest):
    """Synthesize text using Kokoro (am_fenrir) and return base64 WAV with word timestamps."""
    if not req.text or not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty."
        )
    try:
        logger.info("Synthesizing voice audio with Kokoro (%d chars, speed=%.2f)", len(req.text), req.speed or 0.94)
        result = voice_service.synthesize_with_timestamps(req.text, speed=req.speed)
        return result
    except Exception as e:
        logger.exception("Voice synthesis failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice synthesis failed: {str(e)}"
        )

# ─── LinkedIn Analyzer Endpoints ───────────────────────────────────────────
class LinkedInAnalyzeRequest(BaseModel):
    url: Optional[str] = ""
    title: Optional[str] = ""
    candidate_name: Optional[str] = ""
    headline: Optional[str] = ""
    location: Optional[str] = ""
    about: Optional[str] = ""
    experience_raw: Optional[str] = ""
    skills_raw: Optional[str] = ""
    full_text: Optional[str] = ""

@app.post("/api/linkedin/analyze")
def analyze_linkedin_profile(req: LinkedInAnalyzeRequest):
    """Analyze scraped LinkedIn candidate data using Qwen3 and store the result."""
    global LATEST_LINKEDIN_PROFILE
    try:
        logger.info("Analyzing LinkedIn candidate profile: %s", req.candidate_name or req.title)
        analysis = screener.analyze_linkedin_profile(req.model_dump())
        LATEST_LINKEDIN_PROFILE = analysis
        return analysis
    except Exception as e:
        logger.exception("Failed to analyze LinkedIn profile: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LinkedIn analysis failed: {str(e)}"
        )

@app.get("/api/linkedin/profile")
def get_latest_linkedin_profile():
    """Retrieve the latest analyzed LinkedIn profile."""
    return LATEST_LINKEDIN_PROFILE

# ─── Resume Screener Endpoints ─────────────────────────────────────────────
class ResumeTargetRequest(BaseModel):
    title: Optional[str] = "General Role"
    url: Optional[str] = ""
    content: Optional[str] = ""

@app.post("/api/resume/target")
def set_resume_target(req: ResumeTargetRequest):
    """Set the target role / job description captured from the browser."""
    global LATEST_RESUME_TARGET
    logger.info("Setting target role for Resume Screener: %s", req.title)
    LATEST_RESUME_TARGET = req.model_dump()
    return {"status": "success", "target_role": req.title}

@app.get("/api/resume/target")
def get_resume_target():
    """Retrieve current target role / job requirements."""
    return LATEST_RESUME_TARGET

class ResumeScreenRequest(BaseModel):
    resume_text: str = Field(..., description="Full text of the candidate resume")
    target_role: Optional[str] = Field(default="", description="Target job title or role")
    job_description: Optional[str] = Field(default="", description="Job description or requirements")
    comparison_context: Optional[str] = Field(default="", description="Optional benchmark profile")

@app.post("/api/resume/screen")
def screen_resume(req: ResumeScreenRequest):
    """Screen and score a candidate resume across the 4 core criteria."""
    global LATEST_RESUME_ANALYSIS
    if not req.resume_text or len(req.resume_text.strip()) < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text is too short to evaluate."
        )
    try:
        # Fallback to stored target role if not explicitly provided
        effective_role = req.target_role or LATEST_RESUME_TARGET.get("title") or ""
        effective_jd = req.job_description or LATEST_RESUME_TARGET.get("content") or ""

        logger.info("Screening resume (target role: '%s', length: %d chars)", effective_role, len(req.resume_text))
        result = screener.screen_resume(
            resume_text=req.resume_text,
            target_role=effective_role,
            job_description=effective_jd,
            comparison_context=req.comparison_context
        )
        LATEST_RESUME_ANALYSIS = result
        return result
    except Exception as e:
        logger.exception("Resume screening failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume screening failed: {str(e)}"
        )

@app.get("/api/resume/latest")
def get_latest_resume_analysis():
    """Retrieve the latest resume screening and scoring report."""
    return LATEST_RESUME_ANALYSIS

@app.post("/api/document/extract")
async def extract_document(file: UploadFile = File(...)):
    """Extract clean text from an uploaded document (PDF, Word DOCX/DOC, TXT, MD)."""
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )
        text = extract_document_text(content_bytes, file.filename or "document.txt")
        logger.info("Extracted %d characters from uploaded file '%s'", len(text), file.filename)
        return {
            "status": "ok",
            "filename": file.filename,
            "text": text,
            "length": len(text)
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to extract document %s: %s", file.filename, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract text from document: {str(e)}"
        )

@app.post("/api/resume/upload-and-screen")
async def upload_and_screen_resume(
    file: UploadFile = File(...),
    target_role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None)
):
    """Extract text from PDF / Word document and immediately screen it."""
    global LATEST_RESUME_ANALYSIS
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
            
        resume_text = extract_document_text(content_bytes, file.filename or "resume.pdf")
        if not resume_text or len(resume_text.strip()) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Extracted resume text is too short or unreadable."
            )
            
        effective_role = target_role or LATEST_RESUME_TARGET.get("title") or ""
        effective_jd = job_description or LATEST_RESUME_TARGET.get("content") or ""
        
        logger.info("Screening uploaded resume '%s' (%d chars) for target role '%s'", file.filename, len(resume_text), effective_role)
        result = screener.screen_resume(
            resume_text=resume_text,
            target_role=effective_role,
            job_description=effective_jd
        )
        LATEST_RESUME_ANALYSIS = result
        return {
            "status": "ok",
            "filename": file.filename,
            "extracted_text": resume_text,
            "analysis": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to upload and screen resume: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and screen resume: {str(e)}"
        )


CURRENT_ACTIVE_VIEW: str = "summariser"

@app.get("/api/app/active-view")
def get_active_view():
    """Retrieve the current active view for the companion window."""
    return {"active_view": CURRENT_ACTIVE_VIEW}

class ActiveViewRequest(BaseModel):
    view: str = Field(..., description="Target view mode: summariser, resume, linkedin, or history")

@app.post("/api/app/active-view")
def set_active_view(req: ActiveViewRequest):
    """Set the active view mode."""
    global CURRENT_ACTIVE_VIEW
    if req.view in ("summariser", "resume", "linkedin", "history"):
        CURRENT_ACTIVE_VIEW = req.view
    return {"active_view": CURRENT_ACTIVE_VIEW}

def bring_wreciser_window_to_front() -> bool:
    """Bring the existing Wrecziser window to the foreground. Returns True if window was found."""
    found = [False]
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        def enum_cb(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value
            # NEVER match console, terminal, or command prompt windows
            if class_name in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow"):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if title == "Wrecziser":
                    # 1. Restore if minimized
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    
                    # 2. Attach thread input to bypass Windows foreground restriction
                    fg_hwnd = user32.GetForegroundWindow()
                    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
                    app_thread = user32.GetWindowThreadProcessId(hwnd, None)
                    cur_thread = kernel32.GetCurrentThreadId()
                    
                    if fg_thread and fg_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, fg_thread, True)
                    if app_thread and app_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, app_thread, True)
                        
                    # 3. Temporarily set HWND_TOPMOST then HWND_NOTOPMOST to pop window in front
                    HWND_TOPMOST = -1
                    HWND_NOTOPMOST = -2
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    
                    # 4. Detach thread input
                    if fg_thread and fg_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, fg_thread, False)
                    if app_thread and app_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, app_thread, False)
                        
                    found[0] = True
                    return False
            return True
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        hdesk_default = user32.OpenDesktopW("Default", 0, False, 0x0100)
        if hdesk_default:
            user32.EnumDesktopWindows(hdesk_default, EnumWindowsProc(enum_cb), 0)
            user32.CloseDesktop(hdesk_default)
        if not found[0]:
            user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    except Exception as e:
        logger.debug("Failed to focus window via Win32: %s", e)
    return found[0]

@app.post("/api/app/launch")
@app.get("/api/app/launch")
def launch_tauri_app(view: Optional[str] = None):
    """Launch or focus the native Tauri borderless companion app."""
    global CURRENT_ACTIVE_VIEW
    if view and view in ("summariser", "resume", "linkedin", "history"):
        CURRENT_ACTIVE_VIEW = view

    import os
    import subprocess
    import sys
    import time
    import threading
    from pathlib import Path

    # Check if a visible Wrecziser window is already open
    if bring_wreciser_window_to_front():
        logger.info("Tauri app already active and focused. Switched view to '%s'", CURRENT_ACTIVE_VIEW)
        return {"status": "ok", "already_running": True, "active_view": CURRENT_ACTIVE_VIEW}

    # If an orphaned process is lingering without an active window, kill it before fresh launch
    try:
        subprocess.run('taskkill /F /IM wrecziser.exe /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run('taskkill /F /IM app.exe /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    base_dir = Path(__file__).resolve().parent.parent / "Wrecziser-Window-frontend" / "src-tauri" / "target"
    candidates = [
        Path(__file__).resolve().parent.parent / "wrecziser.exe",
        base_dir / "release" / "app.exe",
        base_dir / "debug" / "app.exe",
    ]

    for exe in candidates:
        if exe.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(exe))
                else:
                    subprocess.Popen([str(exe)])
                logger.info("Launched native Tauri application from %s (view: %s)", exe, CURRENT_ACTIVE_VIEW)
                time.sleep(0.5)
                bring_wreciser_window_to_front()
                return {"status": "ok", "launched": str(exe), "active_view": CURRENT_ACTIVE_VIEW}
            except Exception as e:
                logger.error("Failed to launch %s: %s", exe, e)
    return {"status": "not_found", "message": "Tauri binary not found"}



if __name__ == "__main__":
    logger.info("Starting Wreciser Backend on http://%s:%d", SERVER_HOST, SERVER_PORT)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_config=None)
