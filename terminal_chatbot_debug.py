from openai import OpenAI
import os

print("Key loaded:", os.getenv("OPENAI_API_KEY")[:10], "...")

client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input="Say hello in one sentence."
)

print("\nAI Response:")
print(response.output_text)