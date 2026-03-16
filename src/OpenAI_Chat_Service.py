from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv(override=True)

client = OpenAI()

DEFAULT_CHAT_MODEL = "gpt-5"


def request_openai_response(message, model=DEFAULT_CHAT_MODEL):
    """Call OpenAI Responses API and return raw output text."""
    response = client.responses.create(
        model=model,
        input=message
    )

    return (response.output_text or "").strip()


def create_chat_response(message):
    """Compatibility wrapper used by existing API code paths."""
    output_text = request_openai_response(message)
    if output_text:
        return output_text

    return "I could not generate a response right now."
