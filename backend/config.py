from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = Path(__file__).resolve().parent
RISK_OUT_ROOT = BACKEND_ROOT / 'risk_out'
MODEL_ROOT = RISK_OUT_ROOT / 'models'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_env_file = BACKEND_ROOT / '.env'
if _env_file.exists():
    load_dotenv(_env_file, override=False)

READ_DB_URL: str = os.environ['READ_DB_URL']
WRITE_DB_URL: str = os.environ['WRITE_DB_URL']

GEMINI_API_KEY: str = os.environ['GEMINI_API_KEY']
LLM_PROVIDER: str = os.environ['LLM_PROVIDER']
LLM_MODEL: str = os.environ['LLM_MODEL']

APP_TITLE = 'RAILS Risk Sentinel'
APP_VERSION = '0.1.0'
