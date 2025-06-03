from pydantic import BaseModel
from typing import Optional

class TavilySearchParams(BaseModel):
    query: str
    topic: Optional[str] = "general"
    search_depth: Optional[str] = "basic"
    chunks_per_source: Optional[int] = 3
    max_results: Optional[int] = 1
    days: Optional[int] = 7