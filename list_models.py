import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import LLM_BASE_URL

base_url = LLM_BASE_URL.split("/v1", 1)[0].rstrip("/")
response = requests.get(f"{base_url}/api/tags", timeout=10)
response.raise_for_status()

for model in response.json().get("models", []):
    print(model.get("name", "<unnamed>"))
