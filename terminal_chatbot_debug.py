import pickle

# Load dashboard.pkl for product risk score lookup
DASHBOARD_PKL_PATH = os.path.join("src", "models", "dashboard.pkl")
dashboard_artifacts = None
if os.path.exists(DASHBOARD_PKL_PATH):
    with open(DASHBOARD_PKL_PATH, "rb") as f:
        dashboard_artifacts = pickle.load(f)
    print("✅ dashboard.pkl loaded.")
else:
    print("❌ dashboard.pkl not found.")

def get_product_risk_score(product_name):
    if not dashboard_artifacts:
        return None
    df = dashboard_artifacts.get("enriched_df")
    if df is None:
        return None
    # If DataFrame, search for product name
    try:
        matches = df[df["product_name"].str.lower() == product_name.lower()]
        if not matches.empty:
            return matches.iloc[0]["risk_score"]
    except Exception:
        pass
    return None
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

    # Intercept risk score queries
    if "risk score" in user.lower():
        # Try to extract product name
        import re
        match = re.search(r"risk score of (.+)", user.lower())
        if match:
            product_name = match.group(1).strip()
            score = get_product_risk_score(product_name)
            if score is not None:
                print(f"AI: The risk score for '{product_name}' is {score}.")
                continue
            else:
                print(f"AI: Sorry, I couldn't find a risk score for '{product_name}'.")
                continue

    conversation.append({"role": "user", "content": user})

    response = client.responses.create(
        model="gpt-5",
        input=conversation
    )

    ai_reply = response.output_text

    conversation.append({"role": "assistant", "content": ai_reply})

    print("AI:", ai_reply)