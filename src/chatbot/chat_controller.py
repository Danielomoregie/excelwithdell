from OpenAI_Chat_Service import create_chat_response

from .chat_session import append_message, get_conversation, save_conversation
from .personalization import build_model_input


def _extract_message(payload):
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("message", "")).strip()


def _map_openai_error(exc):
    error_text = str(exc).lower()
    if "401" in error_text or "invalid api key" in error_text or "unauthorized" in error_text:
        return {"response": "AI service authentication failed. Please verify OPENAI_API_KEY in the .env file."}, 502
    if "model" in error_text and ("not found" in error_text or "does not exist" in error_text or "access" in error_text):
        return {"response": "The configured model is unavailable for this API key."}, 502
    return {"response": "Sorry, I could not reach the AI service right now. Please try again in a moment."}, 502


def handle_chat_request(payload, session_store, user_profile=None, artifacts=None):
    """Handle one chat turn with session memory and personalization hooks."""
    message_text = _extract_message(payload)
    if not message_text:
        return {"response": "Please enter a message."}, 400

    conversation = get_conversation(session_store)
    conversation = append_message(conversation, "user", message_text)

    model_input = build_model_input(conversation, user_profile, artifacts=artifacts)

    try:
        answer = create_chat_response(model_input)
    except Exception as exc:
        return _map_openai_error(exc)

    conversation = append_message(conversation, "assistant", answer)
    save_conversation(session_store, conversation)

    return {"response": answer}, 200
