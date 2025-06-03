# In your SlackService file (e.g., services/slack_service.py)
import os
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from dotenv import load_dotenv

from agents.chat_agent import ChatAgent
from llms.llm_provider import LLMProvider # Your LLMProvider
from functions.search import tavily_search as tavily_tool

class SlackService:
    def __init__(self):
        load_dotenv()
        self.SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
        self.SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")

        if not self.SLACK_APP_TOKEN or not self.SLACK_BOT_TOKEN:
            print("CRITICAL: Slack tokens not found.")
            raise ValueError("Missing Slack tokens")

        self.web_client = WebClient(token=self.SLACK_BOT_TOKEN)
        try:
            auth_test_result = self.web_client.auth_test()
            self.bot_user_id = auth_test_result["user_id"]
            self.bot_id = auth_test_result.get("bot_id") # Some events use bot_id
            print(f"[SlackService] Authenticated as bot_user_id: {self.bot_user_id}, bot_id: {self.bot_id}")
        except Exception as e:
            print(f"CRITICAL: Slack auth_test failed: {e}")
            raise

        self.socket_client = SocketModeClient(app_token=self.SLACK_APP_TOKEN, web_client=self.web_client)
        
        llm_provider = LLMProvider()
        tools_for_agent = [tavily_tool] # Add other tools if you have them
        self.chat_agent = ChatAgent(llm_provider=llm_provider, tools=tools_for_agent)
        
        self.socket_client.socket_mode_request_listeners.append(self.process_slack_request)
        print("[SlackService] Initialized and listener registered.")

    def process_slack_request(self, client: SocketModeClient, req: SocketModeRequest):
        if req.type == "events_api":
            response = SocketModeResponse(envelope_id=req.envelope_id) # Acknowledge ASAP
            client.send_socket_mode_response(response)

            event_payload = req.payload.get("event", {})
            event_type = event_payload.get("type")
            user_id = event_payload.get("user") # User who generated the event
            text = event_payload.get("text", "").strip()
            channel_id = event_payload.get("channel")
            channel_type = event_payload.get("channel_type") # e.g., 'im', 'channel', 'mpim'
            message_ts = event_payload.get("ts") # Timestamp of the current message
            thread_ts_from_event = event_payload.get("thread_ts") # Parent thread_ts if message is in a thread

            # Ignore messages from bots (including self) or without essential info
            if event_payload.get("bot_id") or (self.bot_id and event_payload.get("bot_id") == self.bot_id) or (user_id == self.bot_user_id):
                return
            if not all([user_id, channel_id, message_ts, channel_type]):
                return

            # Determine the thread_ts that defines the conversation context for history and replies.
            # If the message is already in a thread, use that thread's ts.
            # Otherwise, the current message's ts will start/define the thread for the reply.
            conversation_thread_ts = thread_ts_from_event or message_ts
            conversation_id = f"{channel_id}_{conversation_thread_ts}"
            
            should_process = False
            actual_text_to_agent = text

            if event_type == "app_mention":
                should_process = True
                # Remove the <@BOT_USER_ID> part
                actual_text_to_agent = text.replace(f"<@{self.bot_user_id}>", "").strip()
                print(f"[Slack AppMention] Conv: {conversation_id}, User: {user_id}, Text: '{actual_text_to_agent}'")

            elif event_type == "message" and event_payload.get("subtype") is None:
                if channel_type == "im": # Direct message to the bot
                    should_process = True
                    print(f"[Slack DM] Conv: {conversation_id}, User: {user_id}, Text: '{text}'")
                # Respond to non-mention messages in threads the bot is already part of
                elif thread_ts_from_event and (conversation_id in self.chat_agent.conversation_memory):
                    should_process = True
                    print(f"[Slack Thread Follow-up] Conv: {conversation_id}, User: {user_id}, Text: '{text}'")
            
            if should_process and actual_text_to_agent: # Ensure there's text to process
                agent_response = self.chat_agent.chat(conversation_id, user_id, actual_text_to_agent)
                try:
                    client.web_client.chat_postMessage(
                        channel=channel_id,
                        text=agent_response,
                        thread_ts=conversation_thread_ts # Crucial: reply in thread
                    )
                    print(f"[Slack Reply Sent] Conv: {conversation_id}, Response: '{agent_response}'")
                except Exception as e:
                    print(f"[Slack] Error sending reply to conv '{conversation_id}': {e}")

        elif req.type == "slash_commands":
            response = SocketModeResponse(envelope_id=req.envelope_id) # Acknowledge
            client.send_socket_mode_response(response)

            payload = req.payload
            command = payload.get("command")
            user_id_slash = payload.get("user_id")
            channel_id_slash = payload.get("channel_id")
            text_payload = payload.get("text", "").strip().lower()

            if not all([command, user_id_slash, channel_id_slash]): return

            print(f"[SlashCommand] User: {user_id_slash} in {channel_id_slash}: '{command} {text_payload}'")
            response_text = "Sorry, I didn't understand that command."

            if command == "/model":
                # Ensure your LLMProvider and ChatAgent._get_llm_for_user can handle these model names
                supported_models = ["openai", "gemini"] # Example, make this dynamic or configurable
                if text_payload in supported_models:
                    response_text = self.chat_agent.switch_model(user_id_slash, text_payload)
                else:
                    response_text = f"Usage: `/model <name>`. Supported: {', '.join(supported_models)}"
            elif command == "/currentmodel":
                 response_text = self.chat_agent.get_current_model_info(user_id_slash)

            try:
                client.web_client.chat_postEphemeral(
                    channel=channel_id_slash, user=user_id_slash, text=response_text
                )
            except Exception as e:
                print(f"[Slack] Error sending ephemeral reply for slash command: {e}")
        
        elif req.type == "hello":
            print("[SlackService] 'hello' event received. Connection healthy.")

    def start(self):
        if not self.SLACK_APP_TOKEN or not self.SLACK_BOT_TOKEN: # Should have been caught in init
            print("[SlackService] Cannot start, Slack tokens are missing.")
            return
        print("[SlackService] Connecting to Slack via Socket Mode...")
        try:
            self.socket_client.connect() # Blocking call
            print("[SlackService] Disconnected from Socket Mode.") # If connect() returns
        except Exception as e:
            print(f"[SlackService] Error during SocketModeClient connect: {e}")
            import traceback
            traceback.print_exc()