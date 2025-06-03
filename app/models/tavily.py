from pydantic import BaseModel, Field
from typing import Optional, Literal

class TavilySearchParams(BaseModel):
    query: str = Field(..., description="The search query string to look up.")
    topic: Optional[Literal["general", "news"]] = Field(
        default="general",
        description=(
            "The category of the search. Use 'news' for real-time updates on topics like politics, sports, "
            "and current events covered by mainstream media. Use 'general' for broader searches that may "
            "include a wide range of sources."
        )
    )
    search_depth: Optional[str] = Field(
        default="basic",
        description="The depth of the search: 'basic' or 'advanced'."
    )
    max_results: Optional[int] = Field(
        default=3,
        description="The maximum number of search results to return."
    )
    days: Optional[int] = Field(
        default=7,
        description="Only return results from the last N days."
    )