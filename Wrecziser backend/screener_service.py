import json
import logging
import re
from typing import Dict, Any, Optional
from ollama_client import OllamaClient

logger = logging.getLogger(__name__)

class ScreenerService:
    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def analyze_linkedin_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a scraped LinkedIn profile and extract structured talent insights."""
        name = data.get("candidate_name") or data.get("title") or "Candidate"
        headline = data.get("headline", "")
        about = data.get("about", "")
        experience = data.get("experience_raw", "")
        skills = data.get("skills_raw", "")
        full_text = data.get("full_text", "")

        prompt = f"""You are an elite executive talent scout and recruitment assessor.
Analyze the following professional LinkedIn profile information and produce a structured assessment.

CANDIDATE NAME: {name}
HEADLINE: {headline}
LOCATION: {data.get('location', '')}
ABOUT / BIO: {about}
EXPERIENCE: {experience}
SKILLS: {skills}
PAGE CONTEXT: {full_text[:3500]}

Return STRICT JSON adhering to this exact schema:
{{
  "candidate_name": "Candidate Full Name",
  "headline": "Current Professional Title or Headline",
  "location": "Geographic Location",
  "url": "{data.get('url', '')}",
  "executive_summary": "A concise 2-3 sentence overview of the candidate's career level, domain expertise, and core value proposition.",
  "skills": ["Skill 1", "Skill 2", "Skill 3", "Skill 4", "Skill 5", "Skill 6"],
  "experience_highlights": [
    "Key accomplishment or role responsibility 1",
    "Key accomplishment or role responsibility 2",
    "Key accomplishment or role responsibility 3"
  ],
  "recommended_roles": ["Role 1", "Role 2", "Role 3"]
}}"""

        raw = self.client.generate(prompt=prompt, format_json=True)
        try:
            parsed = json.loads(raw)
            if not parsed.get("candidate_name") or parsed.get("candidate_name") == "Candidate Full Name":
                parsed["candidate_name"] = name
            if not parsed.get("headline") or parsed.get("headline") == "Current Professional Title or Headline":
                parsed["headline"] = headline
            if not parsed.get("location"):
                parsed["location"] = data.get("location", "")
            parsed["url"] = data.get("url", "")
            return parsed
        except Exception as e:
            logger.warning("Failed to parse JSON for LinkedIn analysis: %s. Raw: %s", e, raw[:200])
            # Fallback regex extraction
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    parsed["candidate_name"] = parsed.get("candidate_name") or name
                    parsed["url"] = data.get("url", "")
                    return parsed
                except Exception:
                    pass
            return {
                "candidate_name": name,
                "headline": headline,
                "location": data.get("location", ""),
                "url": data.get("url", ""),
                "executive_summary": f"Professional profile for {name}. {headline}",
                "skills": [s.strip() for s in skills.split("|") if s.strip()][:8],
                "experience_highlights": [experience[:300]],
                "recommended_roles": [headline or "Specialist"]
            }

    def screen_resume(
        self,
        resume_text: str,
        target_role: Optional[str] = None,
        job_description: Optional[str] = None,
        comparison_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Screen and score a candidate's resume across 4 primary criteria:
        1. How is the resume (overall rating & score)
        2. Strong Points
        3. Weak Points
        4. Suggestions
        """
        target_info = ""
        if target_role:
            target_info += f"\nTARGET ROLE: {target_role}"
        if job_description:
            target_info += f"\nJOB REQUIREMENTS / DESCRIPTION:\n{job_description[:3000]}"
        if comparison_context:
            target_info += f"\nBENCHMARK / COMPARISON PROFILE:\n{comparison_context[:2000]}"

        prompt = f"""You are a senior recruitment director and top-tier ATS resume auditor.
Evaluate the candidate's resume thoroughly against industry standards{' and the target role' if target_role else ''}.

{target_info}

RESUME CONTENT:
{resume_text[:6000]}

Analyze strictly according to these 4 CRITERIA:
1. HOW IS THE RESUME:
   - Provide an overall numerical score (0 to 100) based on impact, clarity, action verbs, and technical fit.
   - An executive verdict badge (e.g., 'Exceptional Match', 'Strong Candidate', 'Promising with Gaps', 'Needs Rework').
   - A 2-3 sentence executive assessment summarizing their overall candidacy.
2. STRONG POINTS:
   - 4 to 6 specific bullet points detailing quantified achievements, technical strengths, leadership, or strong domain experience.
3. WEAK POINTS:
   - 3 to 5 clear bullet points identifying missing metrics, vague responsibilities, keyword gaps, or potential red flags.
4. SUGGESTIONS:
   - 4 to 5 actionable suggestions on how to improve the resume or interview readiness.
   - 1 or 2 concrete bullet point rewrites transforming a weak line into a high-impact Google XYZ formula bullet (Accomplished [X] as measured by [Y] by doing [Z]).

Return STRICT JSON with this exact structure:
{{
  "score": 82,
  "verdict": "Strong Candidate",
  "target_role": "{target_role or 'General Evaluation'}",
  "how_is_resume": "The resume demonstrates solid technical foundations and clear career progression...",
  "strong_points": [
    "Quantified revenue and latency improvements across production deployments",
    "Strong mastery of core technologies and modern architecture patterns"
  ],
  "weak_points": [
    "Several experience bullet points describe duties rather than measurable business outcomes",
    "Lacks explicit mentions of cloud infrastructure or container orchestration"
  ],
  "suggestions": [
    "Replace passive phrases with high-impact action verbs (e.g., 'Architected', 'Spearheaded')",
    "Add explicit metrics and scale indicators to project descriptions"
  ],
  "rewrites": [
    {{
      "original": "Worked on improving system performance",
      "improved": "Optimized SQL indexing and introduced Redis caching, slashing API response time by 45% for 2M daily queries",
      "reason": "Quantifies scale, impact, and specific technical tools used"
    }}
  ]
}}"""

        raw = self.client.generate(prompt=prompt, format_json=True)
        try:
            return json.loads(raw)
        except Exception as e:
            logger.warning("Failed to parse JSON for resume screening: %s. Raw: %s", e, raw[:200])
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {
                "score": 75,
                "verdict": "Good Candidate",
                "target_role": target_role or "General Evaluation",
                "how_is_resume": "The resume has a solid foundation with clear technical skills, but could benefit from more quantifiable outcomes.",
                "strong_points": ["Relevant technical background", "Clear work history timeline"],
                "weak_points": ["Could include more specific metrics", "Descriptions could be more action-oriented"],
                "suggestions": ["Include quantifiable results on key projects", "Align bullet points with targeted role keywords"],
                "rewrites": []
            }
