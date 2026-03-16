from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv(override=True)

client = OpenAI()

# 🔍 DEBUG: check if key is loaded (only show first few chars)
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print("✅ Key loaded:", api_key[:12] + "...")
else:
    print("❌ Key NOT loaded")

conversation = []

print("Chatbot ready. Type exit to quit.\n")

while True:
    user = input("You: ")

    if user.lower() == "exit":
        break

    conversation.append({"role": "user", "content": user})

    response = client.responses.create(
        model="gpt-5",
        input=conversation
    )

    ai_reply = response.output_text

    conversation.append({"role": "assistant", "content": ai_reply})

    print("AI:", ai_reply)