# llms/llm_provider.py
import os
from llama_index.llms.openai import OpenAI
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import LLM
from dotenv import load_dotenv

# Import your custom logger
from utils.logger import get_logger # Make sure this path is correct

# Load environment variables from .env file
load_dotenv()

class LLMProvider:
    """
    Provides instances of LLMs (OpenAI, Gemini) configured with API keys or service accounts.
    This class is designed to be imported and used by other modules, such as FastAPI endpoints or agents.
    """
    def __init__(self):
        """
        Initializes the LLMProvider, loading API keys and credential paths from environment variables.
        """
        # Use your custom logger
        self.logger = get_logger(__name__) # Logs will be prefixed with 'llms.llm_provider'

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        gemini_creds_path = os.getenv("GEMINI_CREDS")
        google_app_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if gemini_creds_path and not google_app_creds:
            self.logger.info(f"GEMINI_CREDS ('{gemini_creds_path}') found. Setting GOOGLE_APPLICATION_CREDENTIALS.")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gemini_creds_path
            self.google_application_credentials = gemini_creds_path
        elif google_app_creds:
            self.google_application_credentials = google_app_creds
            self.logger.info(f"GOOGLE_APPLICATION_CREDENTIALS ('{google_app_creds}') found.")
        else:
            self.google_application_credentials = None

        if not self.openai_api_key:
            self.logger.warning("OPENAI_API_KEY not found in environment variables.")
        if not self.google_application_credentials:
            self.logger.warning("Neither GEMINI_CREDS nor GOOGLE_APPLICATION_CREDENTIALS (for Gemini service account) found in environment variables.")

    def get_llm(self, model_provider: str = "gemini") -> LLM | None:
        """
        Returns an instance of the specified LLM.
        """
        provider_lower = model_provider.lower()
        self.logger.info(f"Attempting to get LLM for provider: {provider_lower}")

        if provider_lower == "openai":
            if not self.openai_api_key:
                self.logger.error("Cannot initialize OpenAI LLM, OPENAI_API_KEY is missing.")
                return None
            try:
                # Using a common recent model, adjust if needed. Ensure it's enabled for your key.
                llm_instance = OpenAI(api_key=self.openai_api_key, model="gpt-4o") 
                self.logger.info(f"Successfully initialized OpenAI LLM (model: gpt-4o).")
                return llm_instance
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI LLM: {e}", exc_info=True)
                return None
        
        elif provider_lower == "gemini":
            if not self.google_application_credentials:
                self.logger.error("Cannot initialize Gemini LLM, GOOGLE_APPLICATION_CREDENTIALS path is missing.")
                self.logger.error("Ensure GEMINI_CREDS or GOOGLE_APPLICATION_CREDENTIALS is set in your .env file and points to your service account JSON.")
                return None
            
            # Using the model name from your original code.
            # Verify "models/gemini-2.0-flash" is a valid and accessible model for your service account.
            # Common alternatives: "models/gemini-pro", "models/gemini-1.5-flash-latest".
            gemini_model_name = "models/gemini-2.0-flash"
            self.logger.info(f"Attempting to initialize Gemini LLM with model: '{gemini_model_name}'.")
            try:
                llm_instance = Gemini(model=gemini_model_name)
                self.logger.info(f"Successfully initialized Gemini LLM (model: {gemini_model_name}).")
                return llm_instance
            except Exception as e:
                self.logger.error(f"Error initializing Gemini LLM (model: {gemini_model_name}): {e}", exc_info=True)
                self.logger.error("Please ensure your GOOGLE_APPLICATION_CREDENTIALS are correctly set up, the service account has the 'Vertex AI User' or 'Generative Language API User' role, and the model name is correct and accessible.")
                return None
        else:
            self.logger.error(f"Unknown model provider '{model_provider}'. Choose 'openai' or 'gemini'.")
            return None

    def test_llm_connection(self, model_provider: str = "gemini") -> bool:
        """
        Tests the connection and basic functionality of the specified LLM provider.

        Args:
            model_provider (str): The name of the model provider to test ('openai' or 'gemini').

        Returns:
            bool: True if the test is successful, False otherwise.
        """
        self.logger.info(f"Attempting LLM connection test for provider: {model_provider}")
        llm = self.get_llm(model_provider=model_provider)

        if not llm:
            self.logger.error(f"LLM Test Failed for {model_provider}: Could not get LLM instance.")
            return False

        test_prompt = "Hello! This is a functionality test. Respond with a short confirmation."
        self.logger.info(f"LLM Test for {model_provider}: Sending prompt: '{test_prompt}'")
        
        try:
            # Using .complete() for a basic non-chat interaction test
            response = llm.complete(test_prompt)
            if response and response.text and response.text.strip():
                self.logger.info(f"LLM Test Successful for {model_provider}. Response snippet: {response.text[:70]}...")
                return True
            else:
                self.logger.error(f"LLM Test Failed for {model_provider}: LLM returned an empty or invalid response. Response object: {response}")
                return False
        except Exception as e:
            self.logger.error(f"LLM Test Failed for {model_provider}: Error during test call with prompt '{test_prompt}': {e}", exc_info=True)
            return False