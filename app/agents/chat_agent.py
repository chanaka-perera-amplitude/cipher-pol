from typing import Dict, List, Optional, Tuple
from llama_index.core.llms import LLM, ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
import json
import os

# Assume LLMProvider is defined elsewhere (e.g., llms.llm_provider)
from llms.llm_provider import LLMProvider # Placeholder for your LLMProvider

class ChatAgent:
    def __init__(self, llm_provider: LLMProvider, tools: List[FunctionTool]):
        self.llm_provider = llm_provider
        self.tools = tools
        
        self.user_active_llm: Dict[str, LLM] = {} 
        self.user_active_model_name: Dict[str, str] = {} 
        
        self.conversation_memory: Dict[str, ChatMemoryBuffer] = {}
        # Stores tuple: (ReActAgent, model_name_used_for_creation)
        self.conversation_agent_details: Dict[str, Tuple[ReActAgent, str]] = {}
        
        self.default_model_name = os.getenv("DEFAULT_MODEL", "gemini") # Or your preferred default

    def _get_or_create_memory(self, conversation_id: str) -> ChatMemoryBuffer:
        if conversation_id not in self.conversation_memory:
            print(f"No memory for conversation {conversation_id}. Creating new.")
            self.conversation_memory[conversation_id] = ChatMemoryBuffer.from_defaults(
                chat_history=[], token_limit=3900 
            )
        return self.conversation_memory[conversation_id]

    def _get_llm_for_user(self, user_id: str) -> Tuple[Optional[LLM], str]:
        """Gets the user's preferred LLM and its name."""
        preferred_model_name = self.user_active_model_name.get(user_id, self.default_model_name)
        llm = self.user_active_llm.get(user_id)

        if not llm or self.user_active_model_name.get(user_id) != preferred_model_name: # If no LLM or model name mismatch
            print(f"Loading LLM '{preferred_model_name}' for user {user_id}.")
            llm = self.llm_provider.get_llm(preferred_model_name)
            if not llm:
                print(f"CRITICAL: LLM '{preferred_model_name}' failed to load for user {user_id}.")
                # Fallback to default if preferred failed and isn't already default
                if preferred_model_name != self.default_model_name:
                    print(f"Attempting to load default LLM '{self.default_model_name}' for user {user_id}.")
                    llm = self.llm_provider.get_llm(self.default_model_name)
                    preferred_model_name = self.default_model_name # Update to actual loaded model
                    if not llm:
                         print(f"CRITICAL: Default LLM '{self.default_model_name}' also failed for user {user_id}.")
                         return None, self.default_model_name # Return None LLM, and the name it tried
                else: # Preferred was default, and it failed
                    return None, preferred_model_name


            self.user_active_llm[user_id] = llm
            self.user_active_model_name[user_id] = preferred_model_name # Store the name of the LLM actually loaded
        
        return llm, preferred_model_name

    def _get_or_create_agent(self, conversation_id: str, user_id: str) -> Optional[ReActAgent]:
        user_llm, user_preferred_model_name = self._get_llm_for_user(user_id)
        if not user_llm:
            print(f"Cannot get/create agent for conv {conversation_id} (user {user_id}): LLM unavailable.")
            return None

        current_agent_details = self.conversation_agent_details.get(conversation_id)
        agent_instance = None
        
        if current_agent_details:
            agent_instance, agent_model_name = current_agent_details
            if agent_model_name != user_preferred_model_name:
                print(f"User {user_id}'s model preference changed to {user_preferred_model_name} (was {agent_model_name}). Recreating agent for conv {conversation_id}.")
                agent_instance = None # Force recreation

        if not agent_instance:
            memory = self._get_or_create_memory(conversation_id)
            print(f"Creating ReActAgent for conv {conversation_id} (user {user_id}) with model {user_preferred_model_name}.")
            try:
                agent_instance = ReActAgent.from_llm(
                    llm=user_llm,
                    tools=self.tools,
                    memory=memory,
                    verbose=True # Set to False in production
                )
                self.conversation_agent_details[conversation_id] = (agent_instance, user_preferred_model_name)
            except Exception as e:
                print(f"Error creating ReActAgent for conv {conversation_id}: {e}")
                return None
        
        return agent_instance

    def switch_model(self, user_id: str, model_name: str) -> str:
        print(f"User {user_id} attempting to switch preferred model to: {model_name}")
        # Attempt to load the new LLM to validate model_name and cache it
        new_llm, actual_loaded_model_name = self._get_llm_for_user(user_id) # Temporarily set preference
        
        # Temporarily update user_active_model_name for _get_llm_for_user to try the new one
        original_model_name = self.user_active_model_name.get(user_id)
        self.user_active_model_name[user_id] = model_name 
        
        new_llm, actual_loaded_model_name = self._get_llm_for_user(user_id)

        if new_llm and actual_loaded_model_name == model_name:
            # self.user_active_llm[user_id] and self.user_active_model_name[user_id] are already set by _get_llm_for_user
            print(f"User {user_id} preferred model switched to: {model_name}.")
            return f"Your preferred model is now {model_name.capitalize()}. This will apply to new conversations and update existing ones on next use."
        else:
            # Revert if switch failed
            if original_model_name:
                self.user_active_model_name[user_id] = original_model_name
            else: # Was using default
                self.user_active_model_name.pop(user_id, None) # Revert to default by removing specific entry
                self.user_active_llm.pop(user_id, None)

            current_model_for_user = self.user_active_model_name.get(user_id, self.default_model_name)
            print(f"Failed to switch preferred model to {model_name} for user {user_id}.")
            return f"Sorry, I couldn't switch to {model_name}. Staying on {current_model_for_user.capitalize()}."

    def _log_chat_history(self, conversation_id: str, user_id_for_model_context: Optional[str] = None):
        memory = self._get_or_create_memory(conversation_id)
        history = memory.get_all()
        
        model_in_use = "N/A"
        agent_details = self.conversation_agent_details.get(conversation_id)
        if agent_details:
            model_in_use = agent_details[1] # Get stored model name
        elif user_id_for_model_context:
            model_in_use = self.user_active_model_name.get(user_id_for_model_context, self.default_model_name)
        
        print(f"\n--- History: Conv: {conversation_id} (User: {user_id_for_model_context or 'N/A'}, Model: {model_in_use}) ---")
        for msg in history:
            role_display = msg.role.value.upper()
            print(f"  {role_display}: {msg.content}")
        print("--- End History Log ---")

    def chat(self, conversation_id: str, user_id: str, message_text: str) -> str:
        print(f"DEBUG: ChatAgent.chat ENTRY - conversation_id='{conversation_id}', user_id='{user_id}', message='{message_text[:50]}...'")
        agent = self._get_or_create_agent(conversation_id, user_id)
        
        if not agent:
            error_msg = "I'm having trouble with my systems for this conversation. Please try again later."
            print(f"Error for conv {conversation_id} (user {user_id}): Agent could not be initialized.")
            # Log user message and error to memory manually
            memory = self._get_or_create_memory(conversation_id)
            memory.put(ChatMessage(role=MessageRole.USER, content=message_text))
            memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=error_msg))
            self._log_chat_history(conversation_id, user_id)
            return error_msg
        
        agent_model_name = self.conversation_agent_details.get(conversation_id, (None, "N/A"))[1]
        print(f"Conv {conversation_id} (User {user_id}, Model: {agent_model_name}): '{message_text}'")
        
        assistant_response_text = ""
        try:
            response = agent.chat(message_text) # Agent updates memory
            assistant_response_text = str(response)
        except Exception as e:
            print(f"Error during ReActAgent chat for conv {conversation_id} (user {user_id}): {e}")
            assistant_response_text = "I encountered an error processing your message. Please try again."
            # If agent.chat fails, the agent might not have saved the assistant's error response.
            # The user's message should be in memory from the agent's process.
            # It's good to ensure the error response is also recorded.
            # ReActAgent often puts its final response (or error) into memory.
            # If not, manual put may be needed: memory.put(ChatMessage(role=MessageRole.ASSISTANT, ...))

        print(f"Agent (Model: {agent_model_name} for conv {conversation_id}): '{assistant_response_text}'")
        self._log_chat_history(conversation_id, user_id)
        return assistant_response_text

    def get_current_model_info(self, user_id: str) -> str:
        model_name = self.user_active_model_name.get(user_id, self.default_model_name)
        return f"Your preferred model is {model_name.capitalize()}. This applies to new and existing conversations. Use `/model <name>` to change."
