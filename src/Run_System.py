import os
import sys

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
ARTIFACTS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")

def main():
    print("=" * 60)
    print("  FusionTech Product Risk Management System")
    print("=" * 60)

    # Step 1: Check if model artifacts exist
    if not os.path.exists(ARTIFACTS_PATH):
        print("\n  No trained model found. Running training pipeline...")
        print("  (This only needs to happen once)\n")
        from Train_Model import main as train
        train()
    else:
        size_mb = os.path.getsize(ARTIFACTS_PATH) / (1024 * 1024)
        print(f"\n  Model artifacts found ({size_mb:.1f} MB). Skipping training.")

    # Step 2: Launch Flask server
    print("\n  Starting dashboard server...\n")
    from Flask_API import start
    start(host="0.0.0.0", port=5050)


if __name__ == "__main__":
    main()
