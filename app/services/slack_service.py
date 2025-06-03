# In your SlackService file (e.g., services/slack_service.py)
import os
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from dotenv import load_dotenv

from agents.chat_agent import ChatAgent # Assuming this path is correct
from llms.llm_provider import LLMProvider # Your LLMProvider
from functions.search import tavily_tool

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
            self.bot_id = auth_test_result.get("bot_id")
            print(f"[SlackService] Authenticated as bot_user_id: {self.bot_user_id}, bot_id: {self.bot_id}")
        except Exception as e:
            print(f"CRITICAL: Slack auth_test failed: {e}")
            raise

        self.socket_client = SocketModeClient(app_token=self.SLACK_APP_TOKEN, web_client=self.web_client)
        
        llm_provider = LLMProvider()
        tools_for_agent = [tavily_tool] 
        self.chat_agent = ChatAgent(llm_provider=llm_provider, tools=tools_for_agent)
        
        self.socket_client.socket_mode_request_listeners.append(self.process_slack_request)
        print("[SlackService] Initialized and listener registered.")

    def process_slack_request(self, client: SocketModeClient, req: SocketModeRequest):
        if req.type == "events_api":
            response = SocketModeResponse(envelope_id=req.envelope_id) 
            client.send_socket_mode_response(response)

            event_payload = req.payload.get("event", {})
            event_type = event_payload.get("type")
            user_id = event_payload.get("user") 
            text = event_payload.get("text", "").strip()
            channel_id = event_payload.get("channel")
            # channel_type might be None for app_mentions, get it here
            channel_type = event_payload.get("channel_type") 
            message_ts = event_payload.get("ts") 
            thread_ts_from_event = event_payload.get("thread_ts")

            print(f"[Slack Event Details] type='{event_type}', channel_id='{channel_id}', message_ts='{message_ts}', thread_ts_from_event='{thread_ts_from_event}', user_id='{user_id}', channel_type_payload='{channel_type}', bot_id_payload='{event_payload.get('bot_id')}'")

            # Filter bot messages
            if event_payload.get("bot_id") or (self.bot_id and event_payload.get("bot_id") == self.bot_id) or (user_id == self.bot_user_id):
                return

            # --- MODIFIED ESSENTIAL INFO CHECK ---
            # Base essential fields for any message-like event we want to process
            if not all([user_id, channel_id, message_ts]):
                print(f"[SlackService] Ignored event: Missing one or more base essential fields (user, channel, ts). User: '{user_id}', Channel: '{channel_id}', TS: '{message_ts}'")
                return
            # channel_type is specifically required if it's a 'message' event (not an app_mention) 
            # to differentiate DMs, etc. It might be None for app_mentions.
            if event_type == "message" and not channel_type:
                print(f"[SlackService] Ignored 'message' event: Missing 'channel_type'. User: '{user_id}', Channel: '{channel_id}', TS: '{message_ts}'")
                return
            # --- END MODIFIED ESSENTIAL INFO CHECK ---

            conversation_thread_ts = thread_ts_from_event or message_ts
            conversation_id = f"{channel_id}_{conversation_thread_ts}"
            
            should_process = False
            actual_text_to_agent = text

            if event_type == "app_mention":
                should_process = True
                # Ensure bot_user_id is available, might need to fetch from self.bot_user_id if not in event
                bot_mention_string = f"<@{self.bot_user_id}>" 
                actual_text_to_agent = text.replace(bot_mention_string, "").strip()
                print(f"[Slack AppMention] ConvID: {conversation_id}, User: {user_id}, Cleaned Text: '{actual_text_to_agent}'")

            elif event_type == "message" and event_payload.get("subtype") is None:
                # By this point, if event_type is "message", channel_type should be present due to the check above
                if channel_type == "im": 
                    should_process = True
                    print(f"[Slack DM] ConvID: {conversation_id}, User: {user_id}, Text: '{text}'")
                elif thread_ts_from_event and (conversation_id in self.chat_agent.conversation_memory):
                    should_process = True
                    print(f"[Slack Thread Follow-up] ConvID: {conversation_id}, User: {user_id}, Text: '{text}'")
            
            if should_process and actual_text_to_agent:
                print(f"[ChatAgent Call] Calling chat_agent.chat with ConvID: '{conversation_id}', UserID: '{user_id}', Text: '{actual_text_to_agent[:100]}...'")
                agent_response = self.chat_agent.chat(conversation_id, user_id, actual_text_to_agent)
                
                print(f"[Slack Prepare Reply] ConvID: '{conversation_id}'")
                print(f"  Replying to channel_id: '{channel_id}'")
                print(f"  Original message_ts: '{message_ts}'")
                print(f"  Original thread_ts_from_event: '{thread_ts_from_event}'")
                print(f"  Calculated conversation_thread_ts (for reply): '{conversation_thread_ts}'")
                print(f"  Agent Response: '{agent_response}'")

                if not agent_response:
                    print(f"[Slack No Reply] Agent returned an empty response for ConvID: '{conversation_id}'. Not sending message to Slack.")
                    return
                try:
                    client.web_client.chat_postMessage(
                        channel=channel_id,
                        text=agent_response,
                        thread_ts=conversation_thread_ts 
                    )
                    print(f"[Slack Reply Sent] ConvID: {conversation_id}, Response: '{agent_response}'")
                except Exception as e:
                    print(f"[Slack] Error sending reply to ConvID '{conversation_id}': {e}")
            elif should_process and not actual_text_to_agent:
                 print(f"[SlackService] Skipped processing for ConvID {conversation_id}: No actual text after cleaning (e.g. mention only with no further text).")
            elif req.type == "slash_commands":
                response = SocketModeResponse(envelope_id=req.envelope_id)
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
                    supported_models = ["openai", "gemini"] 
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
        if not self.SLACK_APP_TOKEN or not self.SLACK_BOT_TOKEN:
            print("[SlackService] Cannot start, Slack tokens are missing.")
            return
        print("[SlackService] Connecting to Slack via Socket Mode...")
        try:
            self.socket_client.connect() 
            print("[SlackService] Disconnected from Socket Mode.") 
        except Exception as e:
            print(f"[SlackService] Error during SocketModeClient connect: {e}")
            import traceback
            traceback.print_exc()