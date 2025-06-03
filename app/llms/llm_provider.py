import os
from llama_index.llms.openai import OpenAI
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import LLM
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class LLMProvider:
    """
    Provides instances of LLMs (OpenAI, Gemini) configured with API keys.
    """
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GOOGLE_API_KEY")

        if not self.openai_api_key:
            print("Warning: OPENAI_API_KEY not found in environment variables.")
        if not self.gemini_api_key:
            print("Warning: GOOGLE_API_KEY (for Gemini) not found in environment variables.")

    def get_llm(self, model_name: str = "gemini") -> LLM | None:
        """
        Returns an instance of the specified LLM.

        Args:
            model_name (str): The name of the model to get ('openai' or 'gemini').
                              Defaults to 'openai'.

        Returns:
            LLM | None: An instance of the LlamaIndex LLM, or None if API key is missing or model unknown.
        """
        if model_name.lower() == "openai":
            if not self.openai_api_key:
                print("Error: Cannot initialize OpenAI LLM, API key is missing.")
                return None
            # You can specify a model like "gpt-3.5-turbo" or "gpt-4"
            return OpenAI(api_key=self.openai_api_key, model="gpt-4.1") 
        elif model_name.lower() == "gemini":
            if not self.gemini_api_key:
                print("Error: Cannot initialize Gemini LLM, API key is missing.")
                return None
            # You can specify a model like "models/gemini-pro"
            return Gemini(api_key=self.gemini_api_key, model_name="models/gemini-2.0-flash")
        else:
            print(f"Error: Unknown model name '{model_name}'. Choose 'openai' or 'gemini'.")
            return None