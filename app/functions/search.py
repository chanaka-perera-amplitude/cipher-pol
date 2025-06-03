import requests
import os
from pydantic import BaseModel, Field # Import Field for descriptions in Pydantic model
from typing import Optional
from utils import logger
from models.tavily import TavilySearchParams

# LlamaIndex import for creating a tool
from llama_index.core.tools import FunctionTool

# 2. Your actual Python function that performs the action
def tavily_search_function(query: str, 
                           topic: Optional[str] = None, # Default to None
                           search_depth: Optional[str] = "basic", 
                           max_results: Optional[int] = 3,
                           ) -> str:
    logger.info(f"Tavily search function called with: query='{query}', topic='{topic}', search_depth='{search_depth}', max_results={max_results}")

    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        logger.error("Tavily API key not found.")
        return "Error: TAVILY_API_KEY not found in environment variables."

    # Construct a more conservative payload, only including parameters if they have values
    # and are known to be generally accepted by the Tavily /search endpoint.
    payload = {
        "query": query,
        "include_answer": True, # Often useful
        # "include_raw_content": False, # Usually defaults to false, can omit
        # "include_images": False, # Removed as it's not a standard search param
    }

    if search_depth: # search_depth is optional but LLM seems to provide it
        payload["search_depth"] = search_depth
    if max_results is not None: # max_results is optional
        payload["max_results"] = max_results
    
    # The 'topic' parameter can be tricky. Only include it if explicitly provided
    # and if you are sure about Tavily's accepted values for it.
    # For now, let's try without it unless the LLM explicitly provides a topic.
    if topic and topic.lower() != "general": # 'general' is often an implicit default
        payload["topic"] = topic
    
    logger.info(f"Calling Tavily API with payload: {payload}")

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {tavily_api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        # Try to get more error detail BEFORE raising for status
        if not response.ok: # Checks for 200-299 status codes
            error_detail = f"Error from Tavily API: Status {response.status_code}"
            try:
                # Tavily often returns JSON error details
                error_json = response.json()
                error_detail += f" - Response: {error_json}"
            except requests.exceptions.JSONDecodeError:
                error_detail += f" - Response: {response.text}" # Fallback to text if not JSON
            logger.error(error_detail)
            response.raise_for_status() # Now raise the exception

        data = response.json()
        
        answer = data.get("answer")
        results = data.get("results", [])
        
        output_parts = []
        if answer:
            output_parts.append(f"Answer: {answer}")

        if results:
            sources_summary = "\nSources:\n" + "\n".join(
                [f"- {r.get('title', 'N/A')}: {r.get('url', 'N/A')}" for r in results[:max_results or 5]] # Use max_results or a default
            )
            output_parts.append(sources_summary)
        
        if not output_parts:
            final_response = "No specific answer or results found from Tavily search."
            logger.info(f"Tavily search successful but no direct answer/results. Payload was: {payload}")
            return final_response
            
        final_response = "\n\n".join(output_parts)
        logger.info(f"Tavily search successful. Response snippet: {final_response[:100]}...")
        return final_response

    except requests.exceptions.HTTPError as e: # Already an HTTPError
        # The detailed logging now happens before raise_for_status,
        # but we can still log the exception object itself.
        logger.error(f"Tavily API HTTPError after attempting to log details: {e}", exc_info=True)
        return f"Error: The search request to Tavily failed with status {e.response.status_code if e.response else 'Unknown'}." # Provide status code if available
    except requests.exceptions.RequestException as e:
        logger.error(f"Tavily API request failed (non-HTTPError): {e}", exc_info=True)
        return f"Error: The search request to Tavily failed: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in tavily_search_function: {e}", exc_info=True)
        return "Error: An unexpected error occurred while performing the search."

# FunctionTool definition remains the same, using TavilySearchParams for fn_schema
tavily_tool = FunctionTool.from_defaults(
    fn=tavily_search_function,
    name="tavily_web_search",
    description=(
        "Use this tool to perform a web search using the Tavily search engine. "
        "It can find information on a wide variety of topics, current events, or specific facts. "
        "Provide a clear search query. You can optionally specify a topic (like 'news' or 'research'), "
        "search depth ('basic' or 'advanced'), and the maximum number of results."
    ),
    fn_schema=TavilySearchParams # This schema guides the LLM and argument parsing
)