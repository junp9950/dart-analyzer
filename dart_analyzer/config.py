from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def get_api_key() -> str:
    key = os.getenv("DART_API_KEY", "").strip()
    if not key:
        print(
            "DART_API_KEY가 설정되어 있지 않습니다.\n"
            "https://opendart.fss.or.kr 에서 무료로 API 키를 발급받은 뒤,\n"
            f"{BASE_DIR / '.env'} 파일에 다음처럼 넣어주세요:\n\n"
            "  DART_API_KEY=발급받은_키\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return key
