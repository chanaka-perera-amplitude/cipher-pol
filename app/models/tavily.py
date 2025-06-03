from pydantic import BaseModel, Field
from typing import Optional

class TavilySearchParams(BaseModel):
    query: str = Field(..., description="The specific search query string the user wants to find information about.")
    topic: Optional[str] = Field(
        default=None, # Changed default to None to make it easier to exclude if not provided
        description="The general topic of the search (e.g., 'news', 'research', 'finance'). Defaults to 'general' if not set by LLM."
    )
    search_depth: Optional[str] = Field(
        default="basic", 
        description="The depth of the search. Can be 'basic' for a quick search or 'advanced' for a more thorough one."
    )
    max_results: Optional[int] = Field(
        default=3, # Changed default to a slightly more common number
        description="The maximum number of search results to return."
    )