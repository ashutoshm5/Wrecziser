from typing import List, Optional
from pydantic import BaseModel, Field

class SummarizeRequest(BaseModel):
    title: Optional[str] = Field(default="", description="Webpage title")
    url: Optional[str] = Field(default="", description="Webpage URL")
    content: str = Field(..., min_length=1, description="Cleaned readable text of the webpage")

class SummarizeResponse(BaseModel):
    title: str = Field(..., description="Cleaned title or identified topic")
    summary: str = Field(..., description="Executive factual summary")
    key_points: List[str] = Field(default_factory=list, description="Key takeaways directly from the page")
    important_facts: List[str] = Field(default_factory=list, description="Specific factual details (names, dates, metrics)")
    status: str = Field(default="success", description="Status indicator")

class HealthResponse(BaseModel):
    status: str = Field(..., description="API operational status")
    ollama_connected: bool = Field(..., description="Whether Ollama host is reachable")
    model_available: bool = Field(..., description="Whether the designated summarization model exists in Ollama")
    model_name: str = Field(..., description="Target model name")
