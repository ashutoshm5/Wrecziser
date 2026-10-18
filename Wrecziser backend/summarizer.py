import json
import logging
import re
from typing import Dict, Any, List
from config import PROMPT_PATH, MAX_CONTENT_CHARS
from ollama_client import OllamaClient
from schemas import SummarizeRequest, SummarizeResponse

logger = logging.getLogger(__name__)

def load_system_prompt() -> str:
    """Load the dedicated comprehensive summarization prompt."""
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    return (
        "You are an expert, highly thorough webpage analysis and summarization engine. "
        "Provide a comprehensive, factual breakdown. Cover all major topics in 5-10+ bullet points. "
        "Return valid JSON containing title, summary, key_points, and important_facts."
    )

def repair_json_string(text: str) -> str:
    """Fix common LLM JSON syntax anomalies such as trailing commas and unescaped newlines."""
    # Remove trailing commas before closing braces/brackets
    repaired = re.sub(r",\s*([\]\}])", r"\1", text)
    return repaired

def regex_fallback_parse(text: str) -> Dict[str, Any]:
    """Fallback parser using regular expressions if standard json.loads fails."""
    logger.warning("Attempting regex fallback extraction for model response.")
    result = {
        "title": "",
        "summary": "",
        "key_points": [],
        "important_facts": []
    }

    # Extract title
    title_match = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
    if title_match:
        result["title"] = title_match.group(1).encode().decode("unicode_escape", "ignore")

    # Extract summary
    summary_match = re.search(r'"summary"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
    if summary_match:
        result["summary"] = summary_match.group(1).encode().decode("unicode_escape", "ignore")

    # Extract key_points array
    kp_match = re.search(r'"key_points"\s*:\s*\[([\s\S]*?)\]', text)
    if kp_match:
        items = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', kp_match.group(1))
        result["key_points"] = [i.encode().decode("unicode_escape", "ignore").strip() for i in items if i.strip()]

    # Extract important_facts array
    facts_match = re.search(r'"important_facts"\s*:\s*\[([\s\S]*?)\]', text)
    if facts_match:
        items = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', facts_match.group(1))
        result["important_facts"] = [i.encode().decode("unicode_escape", "ignore").strip() for i in items if i.strip()]

    # If key_points is still empty, look for bullet points in the raw text
    if not result["key_points"]:
        bullets = re.findall(r'^[•\-\*]\s*(.+)$', text, flags=re.MULTILINE)
        if bullets:
            result["key_points"] = [b.strip() for b in bullets]

    if result["summary"] or result["key_points"]:
        return result

    raise ValueError("Model output could not be parsed as valid JSON.")

def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """Parse JSON from model response, handling markdown fences, trailing commas, and text wraps."""
    clean = raw_text.strip()

    # Strip markdown code blocks if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
    if fence_match:
        clean = fence_match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Try repaired JSON (trailing commas, etc.)
    try:
        return json.loads(repair_json_string(clean))
    except json.JSONDecodeError:
        pass

    # Find first '{' and last '}'
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = clean[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            try:
                return json.loads(repair_json_string(candidate))
            except json.JSONDecodeError:
                pass

    # Final attempt: robust regex extraction
    return regex_fallback_parse(clean)

class WebpageSummarizer:
    def __init__(self, client: OllamaClient = None):
        self.client = client or OllamaClient()
        self.system_prompt = load_system_prompt()

    def summarize(self, request: SummarizeRequest) -> SummarizeResponse:
        """Process webpage content and return structured comprehensive summary."""
        content = request.content.strip()
        if len(content) > MAX_CONTENT_CHARS:
            logger.info("Content truncated from %d to %d chars", len(content), MAX_CONTENT_CHARS)
            content = content[:MAX_CONTENT_CHARS]

        user_prompt = (
            f"Webpage Title: {request.title or 'Unknown'}\n"
            f"Webpage URL: {request.url or 'N/A'}\n\n"
            f"Webpage Content:\n"
            f"{content}\n\n"
            f"Analyze the entire content above. Provide a comprehensive summary with detailed key points covering all distinct sections."
        )

        raw_response = self.client.generate(
            prompt=user_prompt,
            system=self.system_prompt,
            format_json=True
        )

        if not raw_response:
            raise ValueError("Ollama returned an empty response.")

        parsed = extract_json_from_text(raw_response)

        # Ensure types and presence of keys
        title = str(parsed.get("title") or request.title or "Webpage Summary").strip()
        summary = str(parsed.get("summary") or "").strip()

        key_points = parsed.get("key_points") or []
        if isinstance(key_points, str):
            key_points = [key_points]
        elif not isinstance(key_points, list):
            key_points = [str(key_points)]
        key_points = [str(kp).strip() for kp in key_points if str(kp).strip()]

        important_facts = parsed.get("important_facts") or []
        if isinstance(important_facts, str):
            important_facts = [important_facts]
        elif not isinstance(important_facts, list):
            important_facts = [str(important_facts)]
        important_facts = [str(f).strip() for f in important_facts if str(f).strip()]

        return SummarizeResponse(
            title=title,
            summary=summary,
            key_points=key_points,
            important_facts=important_facts,
            status="success"
        )
