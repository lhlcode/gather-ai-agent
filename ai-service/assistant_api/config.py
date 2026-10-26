import os
from pathlib import Path

from dotenv import load_dotenv


# config.py 位于 ai-service/assistant_api 下。
# parents[2] 是 ticket-booking 目录。
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"

def load_api_key() -> str:
    load_dotenv(dotenv_path=ENV_PATH)

    api_key = os.getenv("DS_api")
    if not api_key:
        raise RuntimeError("未读取到 DS_api，请检查环境配置。")

    return api_key
