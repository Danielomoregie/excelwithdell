import os
import sys
import subprocess

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
ARTIFACTS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")

def ensure_dependencies():
    """Install required Python packages if not already installed."""
    print("\n  Checking dependencies...")
    try:
        import flask
        import openai
        import pandas
        import numpy
        print("  ✓ All dependencies installed")
    except ImportError:
        print("  Installing required packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", 
                              os.path.join(os.path.dirname(__file__), "..", "requirements.txt"),
                              "--quiet"])
        print("  ✓ Dependencies installed")

def check_openai_config():
    """Check if OpenAI API key is configured in app config or environment."""
    env_key = os.environ.get("OPENAI_API_KEY", "")

    try:
        from Flask_API import OPENAI_API_KEY as app_key
    except Exception:
        app_key = ""

    if app_key and app_key != "your_key_here":
        if env_key:
            print("  ✓ OpenAI key configured (environment variable present)")
        else:
            print("  ✓ OpenAI key configured in src/Flask_API.py")
        return True

    print("  ⚠ OpenAI API key not configured.")
    print("    Chatbot will use fallback summaries.")
    return False

def main():
    print("=" * 60)
    print("  FusionTech Product Risk Management System")
    print("=" * 60)

    # Step 0: Ensure dependencies
    ensure_dependencies()

    # Step 1: Check if model artifacts exist
    if not os.path.exists(ARTIFACTS_PATH):
        print("\n  No trained model found. Running training pipeline...")
        print("  (This only needs to happen once)\n")
        from Train_Model import main as train
        train()
    else:
        size_mb = os.path.getsize(ARTIFACTS_PATH) / (1024 * 1024)
        print(f"\n  Model artifacts found ({size_mb:.1f} MB). Skipping training.")

    # Step 2: Check OpenAI configuration
    print("\n  Checking OpenAI configuration...")
    check_openai_config()

    # Step 3: Launch Flask server
    print("\n  Starting dashboard server...\n")
    from Flask_API import start
    start(host="0.0.0.0", port=5050)


if __name__ == "__main__":
    main()
