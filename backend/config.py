from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = Path(__file__).resolve().parent
RISK_OUT_ROOT = BACKEND_ROOT / 'risk_out'
MODEL_ROOT = RISK_OUT_ROOT / 'models'

# Ensure backend/ is on sys.path so the risk_sentinel.py compatibility shim
# (needed by the pickled model artifacts) is importable as a top-level module.
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Load .env from the backend/ directory (where the file lives)
_env_file = BACKEND_ROOT / '.env'
if _env_file.exists():
    load_dotenv(_env_file, override=False)

# ---------------------------------------------------------------------------
# Database — read replica holds transactions; write DB for new writes
# ---------------------------------------------------------------------------
READ_DB_URL: str = os.environ['READ_DB_URL']      # required — contains transactions
WRITE_DB_URL: str = os.environ['WRITE_DB_URL']    # required — target for new writes

# ---------------------------------------------------------------------------
# LLM / Gemini
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.environ['GEMINI_API_KEY']
LLM_PROVIDER: str = os.environ['LLM_PROVIDER']    # e.g. "gemini"
LLM_MODEL: str = os.environ['LLM_MODEL']          # e.g. "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_TITLE = 'RAILS Risk Sentinel'
APP_VERSION = '0.1.0'
