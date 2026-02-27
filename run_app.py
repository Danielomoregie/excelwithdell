"""
Entry point to run the Streamlit app.
Run from project root: python run_app.py
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
app_path = PROJECT_ROOT / "ml_pipeline" / "app.py"

if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path), "--server.headless", "true"], cwd=str(PROJECT_ROOT))
