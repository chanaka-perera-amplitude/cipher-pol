import requests
import os 

from models.tavily import TavilySearchParams

def tavily_search(params: TavilySearchParams) -> str:
    # Construct the request payload
    payload = {
        "query": params.query,
        "topic": params.topic,
        "search_depth": params.search_depth,
        "chunks_per_source": params.chunks_per_source,
        "max_results": params.max_results,
        "days": params.days,
        "include_answer": True,
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_domains": [],
        "exclude_domains": [],
    }
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    response = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {tavily_api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    # You can return the answer directly, or format as you wish
    answer = data.get("answer")
    results = data.get("results", [])
    if results:
        urls = "\n".join([f"{r['title']}: {r['url']}" for r in results])
        return f"{answer}\n\nSources:\n{urls}"
    return answer or "No answer found."
