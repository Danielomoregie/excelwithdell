from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

client = OpenAI()

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